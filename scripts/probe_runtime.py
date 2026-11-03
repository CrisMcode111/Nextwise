"""Container readiness probe against this backend only; no direct provider calls."""
import json
from urllib.request import Request, ProxyHandler, HTTPRedirectHandler, build_opener
from runtime_config import settings


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def main():
    try:
        config = settings()
        request = Request(f'http://127.0.0.1:{config.port}/health/ready')
        with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=20 + 2 * config.dependency_timeout) as response:
            body = json.loads(response.read(65_536))
        return 0 if body.get('ready') is True else 1
    except Exception:
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
