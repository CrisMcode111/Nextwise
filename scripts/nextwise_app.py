"""Local Nextwise interface. Python stdlib + existing official H-MEM bridge only."""
import csv
from datetime import datetime, timezone
import getpass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import secrets
import re
import socket
import threading
from urllib.parse import urlsplit, parse_qs
import warnings

import export_zetaris as exporter
import integrate_zetaris as integration
import investigation_memory as memory
import update_discovery as discovery

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
INVESTIGATION = "nemotron-lightning-requirements-extraction"
PORT = 8765
KINDS = dict(zip(exporter.INPUTS, ("project_profile", "investigation", "sources", "evidence_draft",
                                  "evidence_review", "use_case", "evaluation_results", "evaluation_recommendation")))


class LocalHTTPServer(ThreadingHTTPServer):
    # Windows SO_REUSEADDR permits multiple servers on the identical port.
    # Exclusive binding keeps stale instances from capturing authenticated reads.
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        super().server_bind()


class AppError(Exception):
    def __init__(self, code, message, status=503):
        self.code, self.message, self.status = code, message, status


def need(condition, message):
    if not condition:
        raise AppError("integrity", message, 409)


def retrieve_memory(root=memory.DEFAULT_MEMORY_ROOT):
    try:
        result = memory.call_bridge({"operation": "resume", "investigation_id": INVESTIGATION,
                                    "memory_root": str(root)})
    except Exception:
        raise AppError("memory", "Investigation memory is unavailable. Check the local Node runtime and H-MEM store.") from None
    if not result.get("ok"):
        raise AppError("memory", "The persisted investigation could not be retrieved. No local-file substitute was used.")
    return result


def present_case(case, fixture, rubric, recommendation, protocol):
    """Describe saved facts/flags, never rerun scoring or infer semantic equivalence."""
    aliases = dict(re.findall(r"(\w+) aliases (\w+)", protocol))
    facts = case.get("parsed_output", {}).get("facts", [])
    validation = case["validation"]
    rows = []
    for field, expected in fixture["expected_explicit_facts"].items():
        key = aliases.get(field, field)
        recorded = [f for f in facts if aliases.get(f["field"], f["field"]) == key]
        flags = []
        if key in validation.get("missing_requirements", []):
            flags.append("Listed as missing by the saved evaluator.")
        if key in validation.get("invented_or_changed_requirements", []):
            flags.append("Listed as changed by the saved evaluator.")
        if not recorded:
            flags.insert(0, "Not returned in the recorded facts.")
        elif not flags:
            flags.append("Returned; not flagged missing or changed by the saved evaluator.")
        # The field/category correspondence is the existing evaluator's known_categories
        # mapping, used only to surface an already recorded incorrect-unknown flag.
        category = {"meal": "meal", "people_count": "people_count", "ready_within_minutes": "time_limit"}.get(key)
        if category in validation.get("incorrect_unknown_categories", []):
            flags.append(f"Also listed as unknown: {category}. The saved evaluator flags this as incorrect.")
        qualifications = [text for text in recommendation["evaluator_limitations"] if key in text]
        rows.append({"field": field, "expected": expected, "recorded": recorded,
                     "findings": flags, "qualifications": qualifications})
    returned = case.get("parsed_output", {}).get("unknowns", [])
    required = rubric.get("unknowns", [])
    return {"rows": rows, "returned_unknowns": returned, "required_unknowns": required,
            "additional_unknowns": [v for v in returned if v not in required],
            "incorrect_unknowns": validation.get("incorrect_unknown_categories", []),
            "protocol": protocol}


def load_investigation(client, retrieve=retrieve_memory):
    """All displayed investigation rows originate in live Zetaris; memory is checked before combining."""
    mem = retrieve()
    need(mem.get("investigation_id") == INVESTIGATION, "Memory belongs to a different investigation.")
    need(all(kind in mem.get("artifacts", {}) for kind in KINDS.values()), "Memory is missing the completed pilot or recommendation.")
    docs = {name: mem["artifacts"][kind] for name, kind in KINDS.items()}
    hashes = {exporter.INPUTS[name]: mem["artifact_hashes"][kind] for name, kind in KINDS.items()}
    need(all(mem["artifact_paths"][kind] == exporter.INPUTS[name] for name, kind in KINDS.items()), "Memory artifact paths differ from the selected snapshot.")
    need(docs["results"]["run_id"] == exporter.RUN_ID, "Memory and selected pilot run differ.")
    manifest = json.loads((integration.SNAPSHOT / "manifest.json").read_text(encoding="utf-8"))
    need({i["path"]: i["sha256"] for i in manifest["inputs"]} == hashes, "Memory and exported investigation identities differ.")
    try:
        exporter.validate_inputs(docs, hashes)
    except Exception:
        raise AppError("integrity", "The retrieved artifact relationships or hashes do not match.", 409) from None
    projections = exporter.project(docs, hashes)
    live, checks = {}, {}
    for table in integration.TABLES:
        names, rows = client.sql(f"SELECT * FROM nextwise.{table}")
        if not rows:
            raise AppError("empty", f"No rows were returned for {table.replace('_', ' ')}. Nothing was substituted.", 404)
        expected = list(csv.DictReader(io.StringIO(exporter.csv_bytes(projections[table]).decode("utf-8"), newline="")))
        try:
            live[table], checks[table] = integration.compare_rows(table, manifest["tables"][table], expected, names, rows)
        except Exception:
            raise AppError("integrity", f"Live {table.replace('_', ' ')} values differ from the persisted investigation. The views were not combined.", 409) from None
    try:
        integration.references(live)
        for table in ("project_profiles", "evaluation_cases"):
            names, rows = client.sql(integration.numeric_sql(table, manifest["tables"][table]))
            integration.validate_numeric(table, manifest["tables"][table], live[table], names, rows)
        names, rows = client.sql(integration.QUERY.read_text(encoding="utf-8"))
        integration.compare_join(integration.expected_join(live), names, rows)
    except Exception:
        raise AppError("integrity", "Numeric conversions, live references or aggregated results could not be reconciled.", 409) from None
    joined = [dict(zip(names, row)) for row in rows]
    profile = json.loads(live["project_profiles"][0]["record_json"])
    investigation = json.loads(live["investigations"][0]["record_json"])
    review = json.loads(live["evidence_reviews"][0]["record_json"])
    claims = sorted(live["evidence_claims"], key=lambda c: int(c["claim_pointer"].split("/")[-1]))
    source_rows = live["sources"]
    sources = [json.loads(row["record_json"]) for row in source_rows]
    for source in sources:
        source["publisher_domain"] = ".".join((urlsplit(source["requested_url"]).hostname or "").split(".")[-2:])
    cases = []
    rec = json.loads(live["evaluation_cases"][0]["recommendation_json"])
    for row in live["evaluation_cases"]:
        case = json.loads(row["record_json"])
        fixture = next(f for f in docs["results"]["fixtures"] if f["id"] == case["fixture_id"])
        finding = next(f for f in rec["evaluation_findings"] if f["fixture_id"] == case["fixture_id"])
        index = next(n for n,c in enumerate(docs["results"]["cases"]) if c["fixture_id"] == case["fixture_id"])
        need(finding["results_pointer"] == f"/cases/{index}", "Recommendation finding points to a different case.")
        case.update(input=fixture["snapshot"]["input"], label=fixture["snapshot"]["label"], finding=finding["finding"])
        case["comparison"] = present_case(case, fixture["snapshot"], docs["results"]["local_rubric"][case["fixture_id"]],
                                          rec, docs["results"]["scoring_protocol"])
        cases.append(case)
    for claim in claims:
        index = int(claim["claim_pointer"].split("/")[-1])
        cr = review["claim_reviews"][index]
        excerpt = docs["draft"]["source_excerpts"][int(cr["quote_reference"]["excerpt_pointer"].split("/")[2])]["excerpt"]
        need(claim["exact_supporting_quote"] in excerpt, "A quotation no longer matches its saved excerpt.")
        claim["review"] = cr
    return {"profile": profile, "investigation": investigation, "sources": sources, "claims": claims,
            "review": review, "cases": cases, "recommendation": rec, "aggregate": joined[0],
            "task": docs["use_case"]["investigated_task"],
            "unknowns": docs["use_case"]["proposed_success_measures"],
            "analysis_observation": mem["analysis_observation"],
            "diagnostics": {"loaded_at": datetime.now(timezone.utc).isoformat(), "run_id": exporter.RUN_ID,
                            "investigation_id": INVESTIGATION, "manifest_id": mem["manifest_id"],
                            "memory_ids": mem["artifact_ids"], "artifact_hashes": mem["artifact_hashes"],
                            "upstream_commit": mem["upstream_commit"], "table_checks": checks,
                            "query_rows": len(joined), "lineage": "Live rows match exact H-MEM artifact identities; numeric casts and aggregate joins reconciled."}}


class State:
    def __init__(self, memory_root=None):
        self.key = None
        self.lock = threading.Lock()
        self.need_key = threading.Event()
        self.need_key.set()
        self.cookie = secrets.token_urlsafe(32)
        self.memory_root = Path(memory_root or memory.DEFAULT_MEMORY_ROOT).resolve()
        self.context = None
        self.evidence_warning = False
        self.discovery = discovery.Store(self.memory_root)
        self.discovery_lock = threading.Lock()
        self.discovery_status = {"running": False, "message": "Ready for a manual check."}
        self.tool_existing_items = None
        self.tool_preview = None  # Process memory only; never sent to H-MEM.


def decision_call(state, operation, **fields):
    try:
        result = memory.call_bridge({"operation": operation, "investigation_id": INVESTIGATION,
                                     "memory_root": str(state.memory_root), **fields})
    except Exception:
        raise AppError("decision_storage", "Decision storage is unavailable. Your typed text has been kept for retry.") from None
    if not result.get("ok"):
        error = result.get("error", {})
        code = error.get("code", "decision_storage")
        allowed = {"invalid_decision", "idempotency_conflict", "decision_conflict", "evidence_changed", "decision_integrity",
                   "missing_evidence", "evidence_mismatch", "persistence_unconfirmed", "memory_locked", "decision_missing"}
        if code not in allowed:
            raise AppError("decision_storage", "The decision could not be confirmed. Your text has been kept. Check H-MEM storage and retry.")
        raise AppError(code, error["message"], 400 if code == "invalid_decision" else 409)
    if "history" in result and state.evidence_warning:
        for record in result["history"]:
            record["needs_review"] = True
            record["integrity_issues"].append("Live evidence could not be reconciled with the referenced snapshot")
    return result


def make_handler(state, loader=None):
    loader = loader or (lambda client: load_investigation(client, lambda: retrieve_memory(state.memory_root)))
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"  # Length-framed responses avoid truncated bodies on Windows close.

        def log_message(self, *args):
            pass  # No URLs, headers, request bodies, credentials or external content in logs.

        def respond(self, status, payload, content_type="application/json; charset=utf-8", cookie=False):
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if content_type.startswith("application/json") else payload
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            if cookie:
                self.send_header("Set-Cookie", f"nextwise={state.cookie}; HttpOnly; SameSite=Strict; Path=/")
            self.end_headers()
            self.wfile.write(data)

        def allowed(self, session=False, post=False):
            hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if self.headers.get("Host") not in hosts or self.headers.get("Sec-Fetch-Site") == "cross-site":
                self.respond(403, {"code": "origin", "message": "Open Nextwise directly on its local address."})
                return False
            if session and f"nextwise={state.cookie}" not in self.headers.get("Cookie", "").split("; "):
                self.respond(401, {"code": "authentication", "message": "Open the local Nextwise page to begin a session."})
                return False
            if post and self.headers.get("Origin") not in {"http://"+host for host in hosts}:
                self.respond(403, {"code": "origin", "message": "This request must come from the local Nextwise page."})
                return False
            return True

        def do_GET(self):
            if not self.allowed():
                return
            route = urlsplit(self.path)
            if route.path == '/api/discovery' and route.query == 'scope=tools':
                if not self.allowed(session=True): return
                self.respond(200, {'status':dict(state.discovery_status), 'tool_preview':state.tool_preview})
                return
            if route.path == "/api/discovery":
                if not self.allowed(session=True): return
                if (state.discovery.directory/'discovery-run.lock').exists():
                    self.respond(200,{"status":{"running":True,"message":"Discovery or bounded semantic assessment is running; the current investigation is preserved."},"scope":discovery.config()})
                    return
                if not state.discovery_lock.acquire(blocking=False):
                    self.respond(200, {"status": {**state.discovery_status, "running": True}, "scope": discovery.config()})
                    return
                if not state.lock.acquire(blocking=False):
                    state.discovery_lock.release()
                    self.respond(200,{"status":{"running":True,"message":"Waiting for the existing investigation read before verifying semantic context."},"scope":discovery.config()})
                    return
                try:
                    import opportunity_workflow as opportunities
                    saved = state.discovery.reassess()
                    state.tool_existing_items = list(saved['items'].values())
                    self.respond(200, {"status": dict(state.discovery_status), "scope": discovery.config(), "semantic_review_supported":True,
                                       "discovery": saved, "opportunities": opportunities.view(state.discovery, saved)})
                except Exception:
                    self.respond(503, {"message": "Discovery memory is unavailable. Check H-MEM runtime/storage and retry; no baseline was replaced."})
                finally:
                    state.lock.release()
                    state.discovery_lock.release()
                return
            if route.path in ("/api/decisions", "/api/decision-evidence"):
                if not self.allowed(session=True):
                    return
                if not state.lock.acquire(blocking=False):
                    self.respond(409, {"code": "loading", "message": "The investigation is loading. Retry decision history in a moment."})
                    return
                try:
                    if route.path == "/api/decisions":
                        self.respond(200, decision_call(state, "decision_history"))
                    else:
                        params = parse_qs(route.query)
                        result = decision_call(state, "decision_evidence", decision_id=params.get("id", [""])[0], kind=params.get("kind", [""])[0])
                        self.respond(200, json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8"), "text/plain; charset=utf-8")
                except AppError as exc:
                    self.respond(exc.status, {"code": exc.code, "message": exc.message})
                finally:
                    state.lock.release()
                return
            paths = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                     "/style.css": ("style.css", "text/css; charset=utf-8")}
            if self.path in paths:
                file, kind = paths[self.path]
                self.respond(200, (WEB/file).read_bytes(), kind, cookie=self.path == "/")
            elif self.path == "/api/status":
                if self.allowed(session=True):
                    self.respond(200, {"authenticated": state.key is not None})
            else:
                self.respond(404, {"code": "missing", "message": "Page not found."})

        def do_POST(self):
            if not self.allowed(session=True, post=True):
                return
            if self.path in ('/api/discovery/recommend', '/api/discovery/decision'):
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 20000 or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                        raise ValueError('Invalid opportunity request.')
                    body = json.loads(self.rfile.read(length).decode('utf-8'))
                    if not isinstance(body, dict): raise ValueError('Invalid opportunity request.')
                except (ValueError, UnicodeError):
                    self.respond(400, {'message': 'Invalid opportunity request; keep the form within its limits.'})
                    return
                if not state.discovery_lock.acquire(blocking=False):
                    self.respond(409, {'message': 'Discovery is busy; your draft is preserved. Retry when it finishes.'})
                    return
                if not state.lock.acquire(blocking=False):
                    state.discovery_lock.release()
                    self.respond(409, {'message': 'The investigation is loading; your draft is preserved. Retry shortly.'})
                    return
                try:
                    import opportunity_workflow as opportunities
                    if self.path.endswith('/recommend'):
                        result = opportunities.prepare(state.discovery, body.get('candidate_id'), body.get('revision_sha256'), body.get('assessment_cache_key'))
                    else:
                        result = opportunities.decide(state.discovery, body)
                    self.respond(200, {'discovery': result, 'opportunities': opportunities.view(state.discovery, result)})
                except ValueError:
                    self.respond(409, {'message': 'The assessment, evidence, decision history or form is no longer valid. Reopen discovery and review the latest briefing; your draft is preserved.'})
                except Exception:
                    self.respond(503, {'message': 'Opportunity persistence could not be confirmed. Keep your draft and reopen saved history before retrying.'})
                finally:
                    state.lock.release()
                    state.discovery_lock.release()
                return
            discovery_path = urlsplit(self.path).path
            tools_only = self.path == '/api/discovery/check?scope=tools'
            if self.path in ("/api/discovery/check", "/api/discovery/select") or tools_only:
                if tools_only and state.tool_existing_items is None:
                    self.respond(409, {'message':'Reopen saved discovery first so existing candidates can be excluded. No feeds were fetched.'})
                    return
                body = None
                if self.path.endswith('/select'):
                    try:
                        length = int(self.headers.get('Content-Length','0'))
                        if not 0 < length <= 10000 or self.headers.get('Content-Type','').split(';')[0] != 'application/json': raise ValueError('Invalid selection request.')
                        body = json.loads(self.rfile.read(length).decode('utf-8'))
                        if not isinstance(body,dict) or not isinstance(body.get('item_id'),str) or not re.fullmatch(r'[0-9a-f]{64}',str(body.get('revision_sha256',''))): raise ValueError('Choose a candidate revision and provide a reason.')
                    except (ValueError, UnicodeError) as exc:
                        self.respond(400,{"message":str(exc)})
                        return
                if not state.discovery_lock.acquire(blocking=False):
                    self.respond(409, {"message": "Discovery or selection is already running. Wait for it to finish."})
                    return
                if discovery_path.endswith('/check'):
                    if tools_only: state.tool_preview = None
                    state.discovery_status = {"running": True, "message": "Starting bounded public-source check…"}
                    def work():
                        try:
                            if tools_only:
                                state.tool_preview = discovery.tool_preview(state.tool_existing_items,
                                    progress=lambda msg: state.discovery_status.update(message=msg))
                                state.discovery_status = {'running':False, 'message':
                                    'Tool candidate check complete. Results are not saved.' if state.tool_preview['status']=='success' else
                                    'Tool candidate check incomplete: some feeds failed. Results are not saved.'}
                                return
                            result = state.discovery.run(progress=lambda msg: state.discovery_status.update(message=msg))
                            state.tool_existing_items = list(result['items'].values())
                            run = result['runs'][-1]
                            state.discovery_status = {"running":False, "message":"Check complete." if run['status']=='success' else "Check incomplete: some sources failed. Successful results were saved; failed-source baselines were retained."}
                        except Exception:
                            state.discovery_status = {"running":False, "message":
                                'Tool preview unavailable. Check the feed configuration; no results were saved.' if tools_only else
                                "Discovery could not be confirmed. Last successful baselines remain. Check H-MEM storage, runtime and locks, then retry.", "failed":True}
                        finally: state.discovery_lock.release()
                    threading.Thread(target=work,daemon=True).start()
                    self.respond(202, {"status":dict(state.discovery_status)})
                else:
                    try:
                        result = state.discovery.select(body['item_id'],body.get('reason'),body['revision_sha256'],body.get('assessment_cache_key'))
                        self.respond(200,{"discovery":result})
                    except (ValueError, UnicodeError) as exc:
                        self.respond(400,{"message":str(exc)})
                    except Exception:
                        self.respond(503,{"message":"Proposal persistence could not be confirmed. Keep your reason and retry after checking H-MEM storage."})
                    finally: state.discovery_lock.release()
                return
            if self.path == "/api/disconnect":
                if not state.lock.acquire(blocking=False):
                    self.respond(409, {"code": "loading", "message": "Wait for the current load to finish."})
                    return
                try:
                    state.key = None
                    state.need_key.set()
                finally:
                    state.lock.release()
                self.respond(200, {"disconnected": True})
                return
            if self.path not in ("/api/load", "/api/decision"):
                self.respond(404, {"code": "missing", "message": "Action not found."})
                return
            if state.key is None:
                self.respond(401, {"code": "authentication", "message": "Enter the masked Zetaris key in the local PowerShell console, then try again."})
                return
            if not state.lock.acquire(blocking=False):
                self.respond(409, {"code": "loading", "message": "The investigation is already loading. Please wait."})
                return
            try:
                body = None
                if self.path == "/api/decision":
                    try:
                        length = int(self.headers.get("Content-Length", "0"))
                        if not 0 < length <= 65536 or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                            raise ValueError()
                        body = json.loads(self.rfile.read(length).decode("utf-8"))
                        if not isinstance(body, dict):
                            raise ValueError()
                        if body.get("choice") not in ("Adopt", "Test", "Defer", "Reject") or not isinstance(body.get("rationale"), str) or not body["rationale"].strip():
                            raise ValueError()
                    except (ValueError, UnicodeError):
                        raise AppError("invalid_decision", "Choose a decision and enter a written rationale. Text must fit within the form limits.", 400)
                state.context = None
                client = integration.Client(state.key)
                try:
                    payload = loader(client)
                    state.context = {key: payload["diagnostics"][key] for key in ("manifest_id", "artifact_hashes", "run_id")} if "diagnostics" in payload else None
                    state.evidence_warning = False
                    if self.path == "/api/decision":
                        if state.context is None or body.get("context") != state.context:
                            raise AppError("evidence_changed", "The evidence context changed. Reload and review it before saving. Your text has been kept.", 409)
                        self.respond(200, decision_call(state, "decision_save", decision=body))
                    else:
                        self.respond(200, payload)
                finally:
                    client._key = None
            except AppError as exc:
                if exc.code in ("integrity", "evidence_changed"):
                    state.evidence_warning = True
                self.respond(exc.status, {"code": exc.code, "message": exc.message})
            except ValueError as exc:
                if "HTTP 401" in str(exc) or "HTTP 403" in str(exc):
                    state.key = None
                    state.need_key.set()
                    self.respond(401, {"code": "authentication", "message": "Zetaris rejected the key or its permissions. Enter a valid key in the private console."})
                else:
                    # Expose only fixed diagnostics, never exception contents or response bodies.
                    http = re.fullmatch(r'HTTP (\d{3}); response body suppressed',str(exc))
                    known = {'Request/JSON decoding failed; body and connection details suppressed': 'The SQL API transport failed or returned non-JSON data.',
                             'Response has no data envelope': 'The SQL API returned no data envelope.',
                             'Unsupported or ambiguous tabular response envelope': 'The SQL API returned an unsupported tabular envelope.'}
                    detail = f'The SQL API returned HTTP {http.group(1)}.' if http else known.get(str(exc),'The SQL service could not complete the query.')
                    self.respond(503, {"code": "zetaris", "message": f"Zetaris could not complete the live read. {detail} Check the service and table access, then retry."})
            except Exception:
                self.respond(503, {"code": "service", "message": "The investigation could not be loaded safely. Check local services and retry; no saved report was substituted."})
            finally:
                state.lock.release()
    return Handler


def main():
    state = State()
    try:
        server = LocalHTTPServer(("127.0.0.1", PORT), make_handler(state))
    except OSError:
        print(f"Nextwise could not bind port {PORT}. If an instance is already running, use it or stop it in its own console before restarting. No credential was requested.",flush=True)
        return
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Nextwise is running at http://127.0.0.1:{PORT}", flush=True)
    print("The API key stays in this process only. Ctrl+C stops the app and clears it.", flush=True)
    try:
        while True:
            state.need_key.wait()
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                key = getpass.getpass("Zetaris API key (hidden): ").strip()
            if key:
                state.key = key
                del key
                state.need_key.clear()
                print("Private key ready. Load or refresh the investigation in Nextwise.", flush=True)
    except (KeyboardInterrupt, EOFError, getpass.GetPassWarning):
        pass
    finally:
        state.key = None
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
