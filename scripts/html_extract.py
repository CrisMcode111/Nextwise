#!/usr/bin/env python3
"""Extract readable text from HTML, preferring article/main content."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "iframe", "canvas"}
VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
CHROME_TAGS = {"nav", "footer", "aside"}
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
CHROME_HINTS = (
    "cookie",
    "onetrust",
    "consent",
    "site-header",
    "topbar",
    "global-nav",
    "breadcrumb",
    "related-news",
    "recent-news",
    "related-posts",
    "social-share",
    "share-dropdown",
    "comments",
    "disqus",
    "newsletter",
    "modal",
    "popup",
)


class Node:
    def __init__(self, tag: str, attrs: dict[str, str]) -> None:
        self.tag = tag
        self.attrs = attrs
        self.children: list[Node | str] = []


def _attr_blob(attrs: dict[str, str]) -> str:
    parts = [
        attrs.get("id", ""),
        attrs.get("class", ""),
        attrs.get("role", ""),
        attrs.get("aria-label", ""),
    ]
    return " ".join(parts).lower()


def is_chrome(node: Node) -> bool:
    if node.tag in CHROME_TAGS:
        return True
    blob = _attr_blob(node.attrs)
    return any(hint in blob for hint in CHROME_HINTS)


class TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("document", {})
        self._stack = [self.root]
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_d = {k.lower(): (v or "") for k, v in attrs}
        if tag in SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        node = Node(tag, attrs_d)
        self._stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self._stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth or tag in VOID_TAGS:
            return
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if self._skip_depth or not data:
            return
        self._stack[-1].children.append(data)


def _text_length(node: Node) -> int:
    total = 0
    for child in node.children:
        if isinstance(child, str):
            total += len(child.strip())
        elif not is_chrome(child) and child.tag not in SKIP_TAGS:
            total += _text_length(child)
    return total


def _find_tags(node: Node, tag: str) -> list[Node]:
    found: list[Node] = []
    if node.tag == tag:
        found.append(node)
    for child in node.children:
        if isinstance(child, Node):
            found.extend(_find_tags(child, tag))
    return found


def _find_content_nodes(node: Node) -> list[Node]:
    """Find candidates without entering navigation or other page chrome.

    Do not discard hidden containers: streamed server-rendered pages can store
    their complete content there, outside an initially empty main element.
    """
    if is_chrome(node) or node.tag in SKIP_TAGS | {"head", "title"}:
        return []
    found = [node]
    for child in node.children:
        if isinstance(child, Node):
            found.extend(_find_content_nodes(child))
    return found


def select_content_root(root: Node) -> Node:
    nodes = _find_content_nodes(root)
    # A main region may contain many independent article cards. Selecting just
    # the largest card loses the rest of a catalog or documentation page.
    mains = [
        node for node in nodes
        if (node.tag == "main" or node.attrs.get("role", "").lower() == "main")
        and _text_length(node) >= 200
    ]
    if mains:
        return max(mains, key=_text_length)

    articles = [node for node in nodes if node.tag == "article" and _text_length(node) >= 200]
    if articles:
        return max(articles, key=_text_length)

    # Some streamed pages leave main empty and put the actual document in a
    # sibling prose container. Read its static HTML without executing scripts.
    prose = [
        node for node in nodes
        if "prose" in node.attrs.get("class", "").lower().split()
        and _text_length(node) >= 200
    ]
    if prose:
        return max(prose, key=_text_length)

    bodies = _find_tags(root, "body")
    if bodies:
        return bodies[0]
    return root


def _collapse_inline(text: str) -> str:
    return re.sub(r"[ \t\r\f\v]+", " ", text).strip()


def render_text(node: Node | str, *, allow_chrome: bool = False) -> str:
    if isinstance(node, str):
        return node.replace("\xa0", " ")

    if node.tag in SKIP_TAGS:
        return ""
    if node.tag in {"head", "title"}:
        return ""
    if not allow_chrome and is_chrome(node) and node.tag not in {"article", "main"}:
        return ""

    inner = "".join(render_text(child) for child in node.children)

    if node.tag == "br":
        return "\n"
    if node.tag == "hr":
        return "\n\n"
    if node.tag in HEADING_TAGS:
        level = int(node.tag[1])
        heading = _collapse_inline(inner)
        if not heading:
            return ""
        return f"\n\n{'#' * level} {heading}\n\n"
    if node.tag == "p":
        paragraph = _collapse_inline(inner)
        return f"\n\n{paragraph}\n\n" if paragraph else ""
    if node.tag == "li":
        item = _collapse_inline(inner)
        return f"\n- {item}" if item else ""
    if node.tag in {"ul", "ol"}:
        return f"\n{inner.strip()}\n"
    if node.tag in {"tr"}:
        cells = [
            _collapse_inline(render_text(child))
            for child in node.children
            if isinstance(child, Node) and child.tag in {"td", "th"}
        ]
        cells = [cell for cell in cells if cell]
        return ("\n" + " | ".join(cells) + "\n") if cells else ""
    if node.tag in {"pre"}:
        return f"\n\n{inner.strip()}\n\n"
    if node.tag in {"blockquote"}:
        quoted = _collapse_inline(inner)
        return f"\n\n> {quoted}\n\n" if quoted else ""
    if node.tag in {"div", "section", "article", "main", "header", "figure", "figcaption", "dl", "dt", "dd"}:
        return f"\n{inner}\n"
    return inner


def normalize_extracted_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [_collapse_inline(line) if line.strip() else "" for line in text.split("\n")]
    compact: list[str] = []
    for line in lines:
        if line:
            compact.append(line)
        elif compact and compact[-1] != "":
            compact.append("")
    return "\n".join(compact).strip()


def extract_readable_text(html: str) -> str:
    builder = TreeBuilder()
    try:
        builder.feed(html)
        builder.close()
    except Exception:
        pass
    root = select_content_root(builder.root)
    rendered = render_text(root, allow_chrome=root.tag in {"article", "main"})
    return normalize_extracted_text(rendered)


def truncate_excerpt(text: str, max_chars: int) -> tuple[str, dict[str, Any]]:
    original_chars = len(text)
    if original_chars <= max_chars:
        return text, {
            "truncated": False,
            "original_chars": original_chars,
            "excerpt_chars": original_chars,
        }
    window = text[:max_chars]
    break_at = max(window.rfind("\n\n"), window.rfind("\n"))
    if break_at >= max_chars // 2:
        excerpt = window[:break_at].rstrip()
    else:
        excerpt = window.rstrip()
    return excerpt, {
        "truncated": True,
        "original_chars": original_chars,
        "excerpt_chars": len(excerpt),
    }
