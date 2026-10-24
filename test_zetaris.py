#!/usr/bin/env python3
"""Simple Zetaris connection test (standard library only)."""

from __future__ import annotations

import getpass
import json
import socket
import sys
import uuid
import urllib.error
import urllib.request

ENDPOINT = "http://localhost:8888/api/v1.0/sql-editor/sqls/run"
TIMEOUT_SECONDS = 60


def contains_one(value: object) -> bool:
    if value == 1 or value == "1":
        return True
    if isinstance(value, dict):
        return any(contains_one(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_one(item) for item in value)
    return False


def main() -> int:
    api_key = getpass.getpass("Zetaris API key: ").strip()
    if not api_key:
        print("Eroare: cheia API este goală.", file=sys.stderr)
        return 1

    request_id = str(uuid.uuid4())
    query_id = str(uuid.uuid4())
    payload = {
        "queryId": query_id,
        "sql": "SELECT 1 AS one",
        "source": "SqlEditor",
        "limit": 1,
    }

    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Org-ID": "1",
            "X-Request-ID": request_id,
        },
    )
    del api_key

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
            status = response.status
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        print(f"Eroare HTTP {exc.code}: {exc.reason}", file=sys.stderr)
        if error_body:
            print(error_body, file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, socket.timeout) or isinstance(exc, TimeoutError):
            print(
                f"Eroare de conexiune: timeout după {TIMEOUT_SECONDS}s către {ENDPOINT}.",
                file=sys.stderr,
            )
        else:
            print(f"Eroare de conexiune: {reason}", file=sys.stderr)
        return 1
    except TimeoutError:
        print(
            f"Eroare de conexiune: timeout după {TIMEOUT_SECONDS}s către {ENDPOINT}.",
            file=sys.stderr,
        )
        return 1
    except OSError as exc:
        print(f"Eroare de conexiune: {exc}", file=sys.stderr)
        return 1

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        print(f"Răspuns HTTP {status}, dar corpul nu este JSON valid:", file=sys.stderr)
        print(body, file=sys.stderr)
        return 1

    if not isinstance(parsed, dict) or "data" not in parsed:
        print("Răspuns neașteptat: lipsește câmpul data.", file=sys.stderr)
        print(json.dumps(parsed, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    data = parsed["data"]
    if not contains_one(data):
        print("Răspuns neașteptat: data nu conține valoarea 1.", file=sys.stderr)
        print(json.dumps(parsed, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    print("Zetaris connection OK")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
