"""Validated unattended entry point. Configuration errors never produce a traceback."""
import sys
from runtime_config import ConfigError, settings


def main():
    try:
        settings()  # Validate before importing modules with configured path constants.
        import nextwise_app
        return nextwise_app.main(['--unattended'])
    except ConfigError as error:
        print(str(error), file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
