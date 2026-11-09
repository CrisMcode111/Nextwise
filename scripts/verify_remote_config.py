"""Offline Compose validation with synthetic settings; no daemon, pulls or writes to data.

Only temporary configuration files are created. Rendered config and Docker stderr
are captured and never displayed, including on failure. No credentials are read.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REMOTE = ROOT / 'deploy/remote'


def require(value, label):
    if not value:
        raise ValueError(label)


def render(files, env_file, cwd):
    environment = {k: v for k, v in os.environ.items()
                   if not k.startswith(('NEXTWISE_', 'COMPOSE_', 'TAVILY_'))}
    command = ['docker', 'compose', '--env-file', str(env_file)]
    for file in files:
        command.extend(['-f', str(file)])
    command.extend(['config', '--format', 'json'])
    result = subprocess.run(command, cwd=cwd, env=environment,
                            capture_output=True, text=True, timeout=30)
    require(result.returncode == 0, 'Compose configuration failed; details suppressed.')
    return json.loads(result.stdout)


def verify():
    with tempfile.TemporaryDirectory(prefix='nextwise-remote-config-') as tmp:
        folder = Path(tmp)
        env_file = folder/'synthetic.env'
        env_file.write_text('\n'.join([
            'NEXTWISE_ARTIFACTS_DIR='+folder.as_posix()+'/artifacts',
            'NEXTWISE_HMEM_DIR='+folder.as_posix()+'/hmem',
            'NEXTWISE_ZETARIS_SECRET_FILE='+folder.as_posix()+'/unset-zetaris-secret',
            'NEXTWISE_TAVILY_SECRET_FILE='+folder.as_posix()+'/unset-tavily-secret',
            'NEXTWISE_METERLESS_SECRET_FILE='+folder.as_posix()+'/unset-meterless-secret',
            'NEXTWISE_ZETARIS_URL=http://127.0.0.1:8888',
            'NEXTWISE_METERLESS_URL=http://127.0.0.1:18088',
        ])+'\n', encoding='utf-8')
        cfg = render([ROOT/'deploy/runtime/compose.yaml', REMOTE/'backend.override.yaml'], env_file, folder)
        require(set(cfg['services']) == {'backend'}, 'Unexpected backend service.')
        backend = cfg['services']['backend']
        require(backend['network_mode'] == 'host' and not backend.get('ports'), 'Host networking or ports mismatch.')
        require(backend['platform'] == 'linux/amd64', 'Image architecture mismatch.')
        require(backend.get('read_only') is True and backend.get('init') is True, 'Runtime isolation changed.')
        require(backend['cap_drop'] == ['ALL'] and 'no-new-privileges:true' in backend['security_opt'], 'Container permissions changed.')
        require(backend.get('command') is None, 'Default full backend entry point was replaced.')
        env = backend['environment']
        require(env['NEXTWISE_HOST'] == '127.0.0.1' and env['NEXTWISE_PORT'] == '8765', 'Backend not loopback-only.')
        require(env['NEXTWISE_ZETARIS_URL'] == 'http://127.0.0.1:8888'
                and env['NEXTWISE_METERLESS_URL'] == 'http://127.0.0.1:18088', 'Service routes incorrect.')
        require(env['NEXTWISE_REQUIRE_METERLESS'] == 'false'
                and env['NEXTWISE_DEPENDENCY_TIMEOUT'] == '15', 'Saved-work readiness defaults changed.')
        require(env['NEXTWISE_ZETARIS_API_KEY_FILE'] == '/run/secrets/zetaris_api_key', 'Zetaris secret-file setting missing.')
        require('TAVILY_API_KEY_FILE' not in env and 'NEXTWISE_METERLESS_TOKEN_FILE' not in env,
                'Disabled providers still require credentials.')
        require(env['NEXTWISE_PROJECT_PROVIDERS_ENABLED'] == 'false'
                and env['NEXTWISE_PROJECT_SEARCH_LIMIT'] == '2'
                and env['NEXTWISE_PROJECT_ASSESSMENT_LIMIT'] == '4', 'Project authorization defaults changed.')
        require(not any(k.endswith(('API_KEY', 'TOKEN')) for k in env), 'Inline credential setting detected.')
        require({s['source'] for s in backend['secrets']} == {'zetaris_api_key'}, 'Disabled providers still mount secrets.')
        mounts = {m['target']: m for m in backend['volumes']}
        require(mounts['/artifacts']['read_only'] and not mounts['/memory'].get('read_only', False), 'Persistence mount permissions wrong.')
        require(mounts['/app/data']['read_only'] and mounts['/app/data']['source'].replace('\\', '/').endswith('/artifacts/data'),
                'Original artifact references are unavailable to the TS decision validator.')
        require(all(not m.get('bind', {}).get('create_host_path', True) for m in mounts.values()), 'Missing paths could be initialized silently.')
        require(not (folder/'artifacts').exists() and not (folder/'hmem').exists(), 'Offline validation created data directories.')

        providers = render([ROOT/'deploy/runtime/compose.yaml', REMOTE/'backend.override.yaml',
                            REMOTE/'providers.override.yaml'], env_file, folder)['services']['backend']
        provider_env = providers['environment']
        require(provider_env['NEXTWISE_REQUIRE_METERLESS'] == 'true', 'Provider route requirement lost.')
        require(provider_env['NEXTWISE_PROJECT_PROVIDERS_ENABLED'] == 'false', 'Providers enabled without explicit opt-in.')
        require(provider_env['TAVILY_API_KEY_FILE'] == '/run/secrets/tavily_api_key'
                and provider_env['NEXTWISE_METERLESS_TOKEN_FILE'] == '/run/secrets/meterless_token', 'Provider secret-file settings missing.')
        require({s['source'] for s in providers['secrets']} == {'zetaris_api_key', 'tavily_api_key', 'meterless_token'},
                'Provider secret mounts changed.')

        # Structural fixture for the privately retained original Zetaris definition.
        # No image is downloaded and no original private .env is accessed.
        base = folder/'zetaris-fixture.yaml'
        base.write_text('''name: zetaris
services:
  postgres:
    image: postgres:16-alpine
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
    healthcheck: {test: [CMD, "true"]}
  init:
    image: synthetic/driver:offline
  driver:
    image: synthetic/driver:offline
    ports: ["10000:10000"]
    depends_on:
      postgres: {condition: service_healthy}
      init: {condition: service_completed_successfully}
    volumes: ["customer-data:/customer-data", "driver-data:/driver-data", "driver-logs:/logs"]
    healthcheck: {test: [CMD, "true"]}
  api:
    image: synthetic/api:offline
    ports: ["0.0.0.0:8888:8888"]
  ui:
    image: synthetic/ui:offline
    ports: ["0.0.0.0:3000:3000"]
  bootstrap:
    image: synthetic/driver:offline
  caddy:
    image: synthetic/caddy:offline
    profiles: [tls]
    ports: ["443:443"]
volumes:
  pgdata: {}
  customer-data: {}
  driver-data: {}
  driver-logs: {}
''', encoding='utf-8')
        zetaris = render([base, REMOTE/'zetaris.restore.override.yaml'], env_file, folder)
        services = zetaris['services']
        require(set(services['driver']['depends_on']) == {'postgres'}, 'Restore still requires initialization.')
        require(not services['driver'].get('ports') and not services['postgres'].get('ports'), 'Database/debug ports exposed.')
        for service, expected in [('api', {8888, 8889}), ('ui', {3000})]:
            ports = services[service]['ports']
            require(all(p['host_ip'] == '127.0.0.1' for p in ports)
                    and {int(p['published']) for p in ports} == expected, 'Zetaris ports are not private.')
        # Some Compose versions omit inactive-profile services from config output.
        for service in ('init', 'bootstrap', 'caddy'):
            if service in services:
                require(services[service].get('profiles') == ['manual-recovery-only'], 'Bootstrap profile not isolated.')
        for name in ('pgdata', 'customer-data', 'driver-data', 'driver-logs'):
            require(zetaris['volumes'][name]['external'] is True
                    and zetaris['volumes'][name]['name'] == 'zetaris_'+name, 'Restore could create an empty volume.')
    return {'status': 'PASS', 'scope': 'offline_compose_only', 'deployments': 0,
            'container_starts': 0, 'volume_mutations': 0, 'credentials_read': 0,
            'verified': ['backend_merge', 'linux_host_routes', 'private_ports', 'secret_file_mounts',
                         'persistent_bind_mounts', 'restored_external_volumes', 'bootstrap_exclusion']}


if __name__ == '__main__':
    try:
        report = verify()
    except Exception as error:
        report = {'status': 'FAIL', 'message': str(error) if type(error) is ValueError else
                  'Offline configuration verification failed; external output suppressed.'}
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['status'] == 'PASS' else 1)
