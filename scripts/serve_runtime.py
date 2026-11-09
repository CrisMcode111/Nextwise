"""Validated unattended entry point. Configuration errors never produce a traceback."""
import sys
from runtime_config import ConfigError, load_native_env, settings


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', help='Explicit private runtime settings for native Python; never evaluated as shell code.')
    parser.add_argument('--projects', action='store_true', help='Project workflows without pilot or Zetaris startup requirements.')
    args = parser.parse_args(argv)
    try:
        if args.env_file:
            load_native_env(args.env_file)
        settings()  # Validate before importing modules with configured path constants.
        import nextwise_app
        return nextwise_app.main(['--unattended'] + (['--projects'] if args.projects else []))
    except ConfigError as error:
        print(str(error), file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
