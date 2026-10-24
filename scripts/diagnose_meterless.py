#!/usr/bin/env python3
"""Run the short baseline and full analysis once, with one hidden token entry."""

from __future__ import annotations

import argparse
import getpass
import json
from pathlib import Path
import sys

import analyze_sources as analyzer

sys.path.insert(0, str(analyzer.ROOT))
import test_meterless as short_test

REPORT_PATH = analyzer.ROOT / "data" / "collected" / "meterless_live_diagnostic.json"


def save_report(report: dict) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-only", action="store_true")
    args = parser.parse_args()
    report = {"started_at_utc": analyzer.utc_now(), "status": "awaiting_token", "tests": []}
    report["request_options"] = {"response_format": {"type": "json_object"},
                                 "chat_template_kwargs": {"enable_thinking": False},
                                 "single_phase": True}
    report["analysis_mode"] = "combined"
    save_report(report)
    if not sys.stdin.isatty():
        print("Run this diagnostic in an interactive terminal for hidden token entry.")
        return 1
    token = getpass.getpass("Meterless Runtime token (hidden): ").strip()
    if not token:
        report["status"] = "empty_token"
        save_report(report)
        return 1

    def record(name, result):
        entry = {"test": name, "ok": result.get("ok"),
                 "http_status": result.get("http_status"),
                 "duration_seconds": result.get("duration_seconds")}
        if not result.get("ok"):
            entry["error"] = result.get("error")
            entry["server_error"] = result.get("server_error", {})
        else:
            content = analyzer.message_content(result["data"])
            entry["content_characters"] = len(content or "")
            entry["has_reasoning_boundary"] = "</think>" in (content or "")
            claims, parse_error = analyzer.parse_claims_payload(content or "")
            entry["claims_json_valid"] = parse_error is None
            entry["claims_count"] = len(claims) if claims is not None else None
            entry["parse_error"] = parse_error
            entry["returned_model"] = analyzer.sanitize_server_text(
                str(result["data"].get("model", "unknown")), token, [],
            )
        report["tests"].append(entry)
        save_report(report)

    if not args.full_only:
        print("1/2: short baseline, one request, no retry.", flush=True)
        report["status"] = "running_short_baseline"
        save_report(report)
        original_max, original_timeout = analyzer.MAX_TOKENS, analyzer.TIMEOUT_SECONDS
        try:
            analyzer.MAX_TOKENS, analyzer.TIMEOUT_SECONDS = 1024, short_test.TIMEOUT_SECONDS
            baseline = analyzer.request_claims(token, [{"role": "user", "content": short_test.USER_MESSAGE}], json_output=False)
        finally:
            analyzer.MAX_TOKENS, analyzer.TIMEOUT_SECONDS = original_max, original_timeout
        record("short_baseline", baseline)
        if not baseline.get("ok") or not analyzer.message_content(baseline.get("data", {})):
            report["status"] = "baseline_failed_full_not_sent"
            save_report(report)
            print("Short baseline failed. Full request was not sent; see the sanitized report.")
            return 1

    print("2/2: existing full analysis, one request, no retry.", flush=True)
    report["status"] = "running_full_analysis"
    save_report(report)
    original_request, original_getpass = analyzer.request_claims, analyzer.getpass.getpass
    original_failure = analyzer.print_failure
    original_argv = sys.argv
    def capture_request(runtime_token, messages, **options):
        result = original_request(runtime_token, messages, **options)
        record("full_analysis", result)
        return result
    def capture_failure(error, *args, **kwargs):
        report["analysis_error"] = analyzer.sanitize_server_text(error, token, [])
        save_report(report)
        return original_failure(error, *args, **kwargs)
    try:
        analyzer.request_claims = capture_request
        analyzer.print_failure = capture_failure
        analyzer.getpass.getpass = lambda *args, **kwargs: token
        sys.argv = ["analyze_sources.py"]
        exit_code = analyzer.main()
    finally:
        analyzer.request_claims, analyzer.getpass.getpass = original_request, original_getpass
        analyzer.print_failure = original_failure
        sys.argv = original_argv
        del token
    report["status"] = "completed" if exit_code == 0 else "full_analysis_failed"
    report["exit_code"] = exit_code
    report["finished_at_utc"] = analyzer.utc_now()
    save_report(report)
    print(f"Sanitized diagnostic report: {REPORT_PATH}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
