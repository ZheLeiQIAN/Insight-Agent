"""Optional Scrapling integration helpers.

Scrapling requires Python 3.10+, while this project still supports Python 3.9.
Keep all imports lazy so the rest of Insight Agent works when Scrapling is not
installed or the runtime is too old.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import Any, List, Optional


MIN_PYTHON = (3, 10)


@dataclass
class ScraplingStatus:
    available: bool
    reason: str = ""


def get_status() -> ScraplingStatus:
    """Return whether Scrapling can be used in the current environment."""
    if sys.version_info < MIN_PYTHON:
        return ScraplingStatus(
            available=False,
            reason="Scrapling 需要 Python 3.10+，当前 Python 版本过低。",
        )

    try:
        import scrapling  # noqa: F401
    except ImportError:
        return ScraplingStatus(
            available=False,
            reason="未安装 Scrapling。请在 Python 3.10+ 环境运行: pip install scrapling",
        )

    return ScraplingStatus(available=True)


def _first_text(selection: Any) -> str:
    """Extract first textual value from a Scrapling selection-like object."""
    if selection is None:
        return ""

    for attr in ("get", "first"):
        fn = getattr(selection, attr, None)
        if callable(fn):
            try:
                value = fn()
                if value is not None:
                    return str(value).strip()
            except Exception:
                pass

    try:
        return str(selection).strip()
    except Exception:
        return ""


def _all_text(selection: Any, limit: int = 100) -> List[str]:
    """Extract a list of text values from a Scrapling selection-like object."""
    if selection is None:
        return []

    values = None
    for attr in ("getall", "all"):
        fn = getattr(selection, attr, None)
        if callable(fn):
            try:
                values = fn()
                break
            except Exception:
                values = None

    if values is None:
        try:
            values = list(selection)
        except Exception:
            values = [_first_text(selection)]

    result = []
    for value in values:
        text = _first_text(value)
        if text:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def fetch_page(url: str, mode: str = "fetcher", **kwargs: Any) -> Any:
    """Fetch a URL with Scrapling and return the page/response object.

    Supported modes:
    - fetcher: lightweight HTTP fetcher
    - dynamic: browser-backed fetcher for JavaScript-heavy pages
    - stealthy: anti-detection browser-backed fetcher
    """
    status = get_status()
    if not status.available:
        raise RuntimeError(status.reason)

    from scrapling.fetchers import DynamicFetcher, Fetcher, StealthyFetcher

    mode = (mode or "fetcher").lower()
    fetcher = {
        "dynamic": DynamicFetcher,
        "stealthy": StealthyFetcher,
        "fetcher": Fetcher,
    }.get(mode, Fetcher)

    return fetcher.fetch(url, **kwargs)


def extract_page_summary(page: Any, max_items: int = 100) -> dict:
    """Extract a conservative structured summary from a Scrapling page."""
    title = _first_text(page.css("title::text")) if hasattr(page, "css") else ""
    headings = []
    paragraphs = []
    links = []

    if hasattr(page, "css"):
        headings = _all_text(page.css("h1::text, h2::text, h3::text"), limit=max_items)
        paragraphs = _all_text(page.css("p::text"), limit=max_items)

        link_nodes = page.css("a")
        try:
            iterable = list(link_nodes)[:max_items]
        except Exception:
            iterable = []
        for node in iterable:
            text = _first_text(node.css("::text")) if hasattr(node, "css") else _first_text(node)
            href = ""
            attrib = getattr(node, "attrib", None)
            if isinstance(attrib, dict):
                href = attrib.get("href", "")
            if text or href:
                links.append({"text": text, "href": href})

    body_text = "\n".join(paragraphs)
    if not body_text:
        try:
            raw = page.text if hasattr(page, "text") else str(page)
            body_text = re.sub(r"\s+", " ", str(raw)).strip()
        except Exception:
            body_text = ""

    return {
        "title": title,
        "headings": headings,
        "paragraphs": paragraphs,
        "links": links,
        "text": body_text,
    }
