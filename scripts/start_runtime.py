"""Start supplied existing service stacks, then the backend. No volume resets or inference."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from runtime_config import CODE_ROOT


def commands(env_file, external_compose=()):
    env_file = Path(env_file).resolve()
    if not env_file.is_file():
        raise ValueError('Provide an existing private --env-file; see deploy/runtime/runtime.env.example.')
    paths = [Path(p).resolve() for p in external_compose]
    if any(not p.is_file() for p in paths):
        raise ValueError('An --external-compose file is missing. Supply the verified existing definition; no service paths are guessed.')
    # External stacks retain their own project directories and .env configuration.
    external = [(p.parent, ['docker', 'compose', '-f', str(p), 'start']) for p in paths]
    backend = ['docker', 'compose', '--env-file', str(env_file), '-f',
               str(CODE_ROOT / 'deploy/runtime/compose.yaml'), 'up', '-d', '--build', '--wait', '--wait-timeout', '120']
    return external + [(CODE_ROOT, backend)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--external-compose', type=Path, action='append', default=[],
                        help='Existing Zetaris or gateway stack; start existing containers only. Repeat for separate stacks.')
    args = parser.parse_args(argv)
    try:
        steps = commands(args.env_file, args.external_compose)
        for cwd, command in steps:
            # Capture external output: supplied service definitions may interpolate secrets.
            result = subprocess.run(command, cwd=cwd, capture_output=True, env=os.environ.copy())
            if result.returncode:
                phase = 'Backend build/readiness' if cwd == CODE_ROOT else 'Existing service container startup'
                print(phase + ' failed. Check Docker availability, supplied service definitions, mount permissions and backend health. External output suppressed to protect secrets.', file=sys.stderr)
                return 1
    except (ValueError, OSError) as error:
        print(str(error) if isinstance(error, ValueError) else 'Docker/Compose could not be started; install/start Docker and Compose v2.', file=sys.stderr)
        return 1
    print('Backend Compose readiness check passed. This is dependency readiness, not proof of successful AI reasoning.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
