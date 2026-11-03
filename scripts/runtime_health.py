"""Read-only dependency diagnostics; never open H-MEM through its auditing bridge."""
import hashlib
import json
import os
import re
import subprocess
import sys

from runtime_config import CODE_ROOT, ConfigError, secret, settings

INVESTIGATION = 'nemotron-lightning-requirements-extraction'


def check_dependencies(config=None, *, network=False, key=None):
    config = config or settings()
    checks = []

    def check(name, operation, error, required=True):
        try:
            operation()
            checks.append({'name': name, 'status': 'ok', 'required': required})
        except Exception:
            checks.append({'name': name, 'status': 'error', 'required': required, 'message': error})

    def need(value):
        if not value:
            raise ValueError()

    check('python', lambda: need(sys.version_info >= (3, 11)), 'Python 3.11 or newer is required.')

    def node():
        # Import the official TS reference without creating H-MEM or invoking the bridge.
        result = subprocess.run([config.node, '--version'], capture_output=True, timeout=5, check=True)
        match = re.fullmatch(rb'v(\d+)\.(\d+)\.(\d+)\s*', result.stdout)
        need(match and int(match[1]) >= 24)
        module = (CODE_ROOT / 'vendor/meterless/hmem/reference/src/index.ts').as_uri()
        subprocess.run([config.node, '--experimental-transform-types', '--input-type=module',
                        '--eval', 'await import(' + json.dumps(module) + ')'],
                       capture_output=True, timeout=10, check=True)
    check('node_hmem_runtime', node, 'Node.js 24+ with TypeScript transformation and the vendored H-MEM module is required.')

    def vendor():
        manifest = json.loads((CODE_ROOT / 'vendor/meterless/upstream.json').read_text(encoding='utf-8'))
        for item in manifest['files']:
            need(hashlib.sha256((CODE_ROOT / item['local_path']).read_bytes()).hexdigest() == item['sha256'])
    check('hmem_vendor', vendor, 'Pinned H-MEM files are missing or differ from upstream.json; restore the pinned files.')

    def artifacts():
        import integrate_zetaris as integration
        # Use the configured snapshot and artifact root; no query, report or export writes.
        need(integration.SNAPSHOT == config.snapshot)
        need(integration.ROOT == config.artifact_root)
        integration.read_snapshot()
    check('pilot_snapshot', artifacts, 'Pilot artifacts/CSV snapshot are missing or fail lineage validation. Restore the existing snapshot; do not regenerate it.')

    def memory():
        for name in (INVESTIGATION, 'update-discovery'):
            folder = config.memory_root / name
            state = json.loads((folder / 'state.json').read_text(encoding='utf-8'))
            need(isinstance(state.get('records'), list) and bool(state['records']) and isinstance(state.get('seq'), int))
            need((folder / 'ledger.jsonl').is_file())
            with (folder / 'ledger.jsonl').open(encoding='utf-8') as ledger:
                for line in ledger:
                    need(isinstance(json.loads(line), dict))
            for file in (folder, folder / 'state.json', folder / 'ledger.jsonl'):
                need(os.access(file, os.W_OK))
        # No locks, imports, bridge reads, repair or write probes are performed.
    check('memory_store', memory, 'Both existing H-MEM stores and ledgers must be readable/writable. Mount the complete private backup; no empty store is initialized.')

    check('zetaris_credentials', lambda: need(key or secret('NEXTWISE_ZETARIS_API_KEY', required=True)),
          'Configure NEXTWISE_ZETARIS_API_KEY or its _FILE secret; credential contents are never reported.')
    if network:
        def sql():
            import integrate_zetaris as integration
            columns, rows = integration.Client(key or secret('NEXTWISE_ZETARIS_API_KEY', required=True),
                                               timeout=config.dependency_timeout).sql('SELECT 1 AS nextwise_health')
            need(len(rows) == 1 and len(rows[0]) == 1 and str(rows[0][0]) == '1')
        check('zetaris_sql', sql, 'Zetaris SQL is unavailable, unauthorized or returned an invalid health result. Check URL, organization, key and service readiness.')
        check('meterless_tcp', config.meterless_probe,
              'Meterless gateway is unreachable. Start the configured gateway; no inference was attempted.',
              required=config.require_meterless)
    else:
        checks.append({'name': 'service_connectivity', 'status': 'not_checked', 'required': False})
    return {'ready': all(c['status'] == 'ok' for c in checks if c['required']),
            'scope': 'dependency_checks_only', 'model_requests': 0, 'checks': checks}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--network', action='store_true', help='Also perform one Zetaris SELECT 1 and a gateway TCP probe; never inference.')
    args = parser.parse_args()
    try:
        report = check_dependencies(network=args.network)
    except ConfigError as error:
        report = {'ready': False, 'message': str(error), 'model_requests': 0}
    print(json.dumps(report, indent=2))
    return 0 if report['ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
