#!/usr/bin/env python3
"""Simple Meterless Runtime connection test (standard library only)."""

from __future__ import annotations

import getpass
import json
import socket
import sys
import urllib.error
import urllib.request

ENDPOINT = "http://127.0.0.1:8088/v1/chat/completions"
TIMEOUT_SECONDS = 120
USER_MESSAGE = "Răspunde exact: Nextwise connection OK"


def main() -> int:
    token = getpass.getpass("Meterless Runtime token: ").strip()
    if not token:
        print("Eroare: tokenul este gol.", file=sys.stderr)
        return 1

    payload = {
        "model": "meterless/auto",
        "stream": False,
        "max_tokens": 1024,
        "messages": [
            {"role": "user", "content": USER_MESSAGE},
        ],
    }

    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "meterless-app": "nextwise",
            "meterless-scope": "user",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    del token

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
        data = json.loads(body)
    except json.JSONDecodeError:
        print(f"Răspuns HTTP {status}, dar corpul nu este JSON valid:", file=sys.stderr)
        print(body, file=sys.stderr)
        return 1

    model = data.get("model")
    choices = data.get("choices") or []
    content = None
    if choices:
        message = choices[0].get("message") or {}
        content = message.get("content")
        if content is None:
            content = choices[0].get("text")

    print(f"model: {model}")
    print("răspuns:")
    print(content if content is not None else body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
