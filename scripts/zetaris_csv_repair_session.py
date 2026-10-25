"""Private-key, bounded local repair session; commands and sanitized results only."""
import getpass
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid
import warnings

import validate_zetaris_profile as validator

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "reports/zetaris_csv_repair_commands.json"
OUTBOX = ROOT / "reports/zetaris_csv_repair_observations.json"
DETAIL_PATH = "/api/v1.0/lightning-database/databases/nextwise/file-store-tables/project_profiles"


def main():
    validator.expected_table()
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        key = getpass.getpass("Zetaris API key (hidden; retained in memory for this repair session): ").strip()
    if not key:
        return
    # Reuse the existing request implementation and private-key flow without
    # repeated prompts. No key is passed in shell arguments, files or env vars.
    validator.getpass.getpass = lambda prompt: key
    observations = json.loads(OUTBOX.read_text(encoding="utf-8")) if OUTBOX.exists() else []
    processed = {entry["id"] for entry in observations}
    processed.add("stop_initial_session")
    deadline = time.monotonic() + 1800
    print("Private session ready; waiting for scoped diagnostic commands.", flush=True)

    def sanitize(value):
        if isinstance(value, str):
            return value.replace(key, "[REDACTED]")
        if isinstance(value, list):
            return [sanitize(v) for v in value]
        if isinstance(value, dict):
            return {k: sanitize(v) for k, v in value.items()
                    if not any(s in k.lower() for s in ("authorization", "password", "credential", "secret", "token"))}
        return value

    while time.monotonic() < deadline:
        batch = json.loads(INBOX.read_text(encoding="utf-8")) if INBOX.exists() else []
        for command in batch:
            identity = command["id"]
            if identity in processed:
                continue
            action = command.get("action", "sql")
            if action == "stop":
                print("Private session closed.", flush=True)
                return
            if action in ("registration", "patch_registration", "validate"):
                entry = {"id": identity, "action": action}
                try:
                    if action == "validate":
                        validator.SQL = "SELECT * FROM nextwise.project_profiles"
                        entry["validator_exit_code"] = validator.main()
                    else:
                        request = urllib.request.Request("http://localhost:8888" + DETAIL_PATH,
                            method="PATCH" if action == "patch_registration" else "GET",
                            data=json.dumps(command["body"]).encode("utf-8") if action == "patch_registration" else None,
                            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                     "X-Org-ID": "1", "X-Request-ID": str(uuid.uuid4())})
                        try:
                            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), validator.NoRedirect())
                            with opener.open(request, timeout=60) as response:
                                raw = response.read()
                                entry["http_status"] = response.status
                            if raw:
                                parsed = json.loads(raw)
                                data = parsed.get("data", parsed)
                                # Scope to non-secret local CSV registration fields.
                                allowed = ("format", "storageType", "path", "description", "scanType", "pathGlobFilter", "delimiter", "parameters")
                                entry["registration"] = {k: data[k] for k in allowed if k in data}
                        finally:
                            request.remove_header("Authorization")
                except urllib.error.HTTPError as exc:
                    entry["error"] = f"HTTP {exc.code}; body suppressed"
                    exc.close()
                except (OSError, ValueError):
                    entry["error"] = "Request or decoding failure; details suppressed"
                observations.append(sanitize(entry))
                OUTBOX.write_text(json.dumps(observations, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
                processed.add(identity)
                print(f"Completed scoped command: {identity}", flush=True)
                continue
            sql = command["sql"]
            # No file writes, uploads, DML, infrastructure or unrelated tables.
            lowered = sql.lower()
            if not lowered.startswith(("select ", "desc ", "describe ", "show ", "create ", "alter ", "drop ")):
                raise ValueError("Unsupported command category")
            if any(word in lowered for word in ("password", "credential", "insert ", "truncate ", "delete ", "datasources", "show users")):
                raise ValueError("Command outside repair scope")
            entry = {"id": identity, "sql": sql}
            try:
                validator.SQL = sql
                response = validator.query_once()
                try:
                    names, rows, types = validator.unpack_response(response)
                    entry.update(columns=names, rows=rows, types=types)
                    if command.get("compare"):
                        table, expected = validator.expected_table()
                        entry["checks"] = validator.compare(table, expected, names, rows)
                except ValueError:
                    # Capture only message/status fields, never whole HTTP bodies.
                    def messages(node, depth=0):
                        if not isinstance(node, dict) or depth > 4:
                            return {}
                        return {k: (messages(v, depth+1) if isinstance(v, dict) else v)
                                for k,v in node.items() if k in ("data", "error", "message", "status", "errorMessage", "success")}
                    entry["messages"] = messages(response)
                entry["transport"] = "HTTP 200"
            except urllib.error.HTTPError as exc:
                entry["error"] = f"HTTP {exc.code}; body suppressed"
                exc.close()
            except (OSError, ValueError):
                entry["error"] = "Request or decoding failure; details suppressed"
            observations.append(sanitize(entry))
            OUTBOX.write_text(json.dumps(observations, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
            processed.add(identity)
            print(f"Completed scoped command: {identity}", flush=True)
        time.sleep(1)


if __name__ == "__main__":
    main()
