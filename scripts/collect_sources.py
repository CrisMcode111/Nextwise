#!/usr/bin/env python3
"""Fetch listed public source URLs once and store local snapshots."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
INVESTIGATION_PATH = ROOT / "data" / "investigation.json"
SOURCES_INDEX_PATH = ROOT / "data" / "sources.json"
SNAPSHOT_DIR = ROOT / "data" / "collected" / "snapshots"
TEXT_DIR = ROOT / "data" / "collected" / "texts"

TIMEOUT_SECONDS = 30
MIN_TEXT_CHARS = 200
USER_AGENT = "NextwiseSourceCollector/1.0 (local research; Python-urllib)"

BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "br",
    "div",
    "dl",
    "dt",
    "dd",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "tr",
    "ul",
}
SKIP_TAGS = {"script", "style", "noscript", "template"}
DATE_META_KEYS = {
    "article:published_time",
    "article:published",
    "og:published_time",
    "og:updated_time",
    "datepublished",
    "datecreated",
    "pubdate",
    "publishdate",
    "publication_date",
    "publish_date",
    "dc.date",
    "dc.date.issued",
    "dcterms.created",
    "dcterms.issued",
    "dcterms.date",
    "citation_publication_date",
    "citation_date",
    "parsely-pub-date",
    "date",
}
DATE_PATTERN = re.compile(
    r"^\s*\d{4}-\d{2}-\d{2}"
    r"(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?"
    r"(?:Z|[+-]\d{2}:?\d{2})?)?\s*$",
    re.IGNORECASE,
)


class PageExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.meta: list[dict[str, str]] = []
        self.time_datetimes: list[str] = []
        self.json_ld_blocks: list[str] = []
        self._skip_depth = 0
        self._in_title = False
        self._in_json_ld = False
        self._json_ld_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_d = {k.lower(): (v or "") for k, v in attrs}
        if tag in SKIP_TAGS:
            self._skip_depth += 1
            if (
                tag == "script"
                and attrs_d.get("type", "").lower() == "application/ld+json"
            ):
                self._in_json_ld = True
                self._json_ld_parts = []
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            self.meta.append(attrs_d)
        elif tag == "time" and attrs_d.get("datetime"):
            self.time_datetimes.append(attrs_d["datetime"])
        elif tag in BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and self._skip_depth:
            if tag == "script" and self._in_json_ld:
                block = "".join(self._json_ld_parts).strip()
                if block:
                    self.json_ld_blocks.append(block)
                self._in_json_ld = False
                self._json_ld_parts = []
            self._skip_depth -= 1
            return
        if tag == "title":
            self._in_title = False
        elif tag in BLOCK_TAGS and not self._skip_depth:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_json_ld:
            self._json_ld_parts.append(data)
            return
        if self._skip_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
        else:
            self.text_parts.append(data)

    def title(self) -> str | None:
        value = " ".join(part.strip() for part in self.title_parts).strip()
        value = re.sub(r"\s+", " ", value)
        return value or None

    def text(self) -> str:
        raw = "".join(self.text_parts)
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.splitlines()]
        compact: list[str] = []
        for line in lines:
            if line:
                compact.append(line)
            elif compact and compact[-1] != "":
                compact.append("")
        return "\n".join(compact).strip()


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def stable_source_id(url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    host = urlparse(url).netloc.replace("www.", "")
    host_slug = re.sub(r"[^a-z0-9]+", "-", host.lower()).strip("-") or "source"
    return f"{host_slug}-{digest}"


def looks_like_date(value: str) -> bool:
    return bool(DATE_PATTERN.match(value.strip()))


def meta_key(attrs: dict[str, str]) -> str:
    for field in ("property", "name", "itemprop", "http-equiv"):
        if attrs.get(field):
            return attrs[field].strip().lower()
    return ""


def dates_from_json_ld(blocks: list[str]) -> list[str]:
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {"datePublished", "dateCreated", "dateModified"} and isinstance(
                    value, str
                ):
                    found.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for block in blocks:
        try:
            walk(json.loads(block))
        except json.JSONDecodeError:
            continue
    return found


def publication_date_from(extractor: PageExtractor) -> str | None:
    candidates: list[str] = []
    for attrs in extractor.meta:
        key = meta_key(attrs)
        content = attrs.get("content", "").strip()
        if key in DATE_META_KEYS and content:
            candidates.append(content)
    candidates.extend(extractor.time_datetimes)
    candidates.extend(dates_from_json_ld(extractor.json_ld_blocks))
    for value in candidates:
        if looks_like_date(value):
            return value.strip()
    return None


def og_title(extractor: PageExtractor) -> str | None:
    for attrs in extractor.meta:
        if meta_key(attrs) in {"og:title", "twitter:title"}:
            value = attrs.get("content", "").strip()
            if value:
                return value
    return None


def extract_page(html: str) -> PageExtractor:
    extractor = PageExtractor()
    try:
        extractor.feed(html)
        extractor.close()
    except Exception:
        # Keep any partial extraction; malformed HTML is recorded via text length.
        pass
    return extractor


def unique_stem(source_id: str, retrieved_at: datetime) -> str:
    stamp = retrieved_at.strftime("%Y%m%dT%H%M%SZ")
    stem = f"{source_id}_{stamp}"
    snapshot = SNAPSHOT_DIR / f"{stem}.html"
    text_file = TEXT_DIR / f"{stem}.txt"
    suffix = 1
    while snapshot.exists() or text_file.exists():
        stem = f"{source_id}_{stamp}_{suffix}"
        snapshot = SNAPSHOT_DIR / f"{stem}.html"
        text_file = TEXT_DIR / f"{stem}.txt"
        suffix += 1
    return stem


def relative_posix(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def fetch_url(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return {
            "ok": False,
            "http_status": None,
            "final_url": None,
            "raw": b"",
            "html": "",
            "error": f"unsupported URL scheme: {parsed.scheme or '(none)'}",
        }

    request = Request(
        url,
        method="GET",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en",
            "Accept-Encoding": "identity",
        },
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            return {
                "ok": True,
                "http_status": getattr(response, "status", None) or response.getcode(),
                "final_url": response.geturl(),
                "raw": raw,
                "html": raw.decode(charset, errors="replace"),
                "error": None,
            }
    except HTTPError as exc:
        raw = exc.read() if exc.fp is not None else b""
        charset = "utf-8"
        if exc.headers is not None:
            charset = exc.headers.get_content_charset() or "utf-8"
        return {
            "ok": False,
            "http_status": exc.code,
            "final_url": exc.geturl() if hasattr(exc, "geturl") else url,
            "raw": raw,
            "html": raw.decode(charset, errors="replace") if raw else "",
            "error": f"HTTP {exc.code}: {exc.reason}",
        }
    except TimeoutError:
        return {
            "ok": False,
            "http_status": None,
            "final_url": None,
            "raw": b"",
            "html": "",
            "error": f"timeout after {TIMEOUT_SECONDS}s",
        }
    except URLError as exc:
        return {
            "ok": False,
            "http_status": None,
            "final_url": None,
            "raw": b"",
            "html": "",
            "error": f"connection error: {exc.reason}",
        }
    except OSError as exc:
        return {
            "ok": False,
            "http_status": None,
            "final_url": None,
            "raw": b"",
            "html": "",
            "error": f"connection error: {exc}",
        }


def collect_one(url: str) -> dict[str, Any]:
    retrieved_at = utc_now()
    source_id = stable_source_id(url)
    fetched = fetch_url(url)
    html = fetched["html"]
    raw = fetched["raw"]
    extractor = extract_page(html) if html else PageExtractor()
    title = extractor.title() or og_title(extractor)
    text = extractor.text()
    publication_date = publication_date_from(extractor) if html else None
    content_sha256 = hashlib.sha256(raw).hexdigest() if raw else None

    snapshot_path = None
    text_path = None
    if raw or html or text:
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        TEXT_DIR.mkdir(parents=True, exist_ok=True)
        stem = unique_stem(source_id, retrieved_at)
        snapshot_file = SNAPSHOT_DIR / f"{stem}.html"
        text_file = TEXT_DIR / f"{stem}.txt"
        snapshot_file.write_bytes(raw if raw else html.encode("utf-8", errors="replace"))
        text_file.write_text(text, encoding="utf-8")
        snapshot_path = relative_posix(snapshot_file)
        text_path = relative_posix(text_file)

    if not fetched["ok"]:
        status = "failed"
        extraction_notes = fetched["error"]
    elif len(text) < MIN_TEXT_CHARS:
        status = "insufficient_content"
        extraction_notes = (
            f"Download succeeded (retrieved, not verified evidence), but extracted "
            f"readable text is only {len(text)} characters (minimum {MIN_TEXT_CHARS}). "
            "The page may be empty, blocked, or rendered mainly by JavaScript."
        )
    else:
        status = "retrieved"
        extraction_notes = (
            "Download succeeded. Status 'retrieved' means a local snapshot was stored; "
            "it is not verified evidence."
        )

    return {
        "id": source_id,
        "requested_url": url,
        "final_url": fetched["final_url"],
        "title": title,
        "retrieved_at_utc": retrieved_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "http_status": fetched["http_status"],
        "content_sha256": content_sha256,
        "snapshot_path": snapshot_path,
        "text_path": text_path,
        "publication_date": publication_date,
        "status": status,
        "error": None if fetched["ok"] else fetched["error"],
        "extraction_notes": extraction_notes,
    }


def load_investigation() -> dict[str, Any]:
    with INVESTIGATION_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def print_report(records: list[dict[str, Any]]) -> None:
    print(f"Collected {len(records)} URL(s). Retrieved means downloaded, not verified evidence.")
    for record in records:
        title = record.get("title") or "(no title)"
        status = record["status"]
        http_status = record.get("http_status")
        print(f"- {record['id']}: {status} HTTP {http_status} | {title}")
        print(f"  {record['requested_url']}")
        if record.get("error"):
            print(f"  error: {record['error']}")
        if record.get("extraction_notes"):
            print(f"  notes: {record['extraction_notes']}")


def main() -> int:
    investigation = load_investigation()
    urls = investigation.get("initial_source_urls") or []
    if not urls:
        print("No initial_source_urls found in data/investigation.json.", file=sys.stderr)
        return 1

    records = []
    for url in urls:
        if not isinstance(url, str) or not url.strip():
            records.append(
                {
                    "id": stable_source_id(str(url)),
                    "requested_url": url,
                    "final_url": None,
                    "title": None,
                    "retrieved_at_utc": utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "http_status": None,
                    "content_sha256": None,
                    "snapshot_path": None,
                    "text_path": None,
                    "publication_date": None,
                    "status": "failed",
                    "error": "empty or invalid URL",
                    "extraction_notes": "empty or invalid URL",
                }
            )
            continue
        records.append(collect_one(url.strip()))

    index = {
        "investigation_id": investigation.get("id"),
        "note": (
            "A successful download is recorded as retrieved. That is not verified evidence."
        ),
        "sources": records,
    }
    SOURCES_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    SOURCES_INDEX_PATH.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print_report(records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
