#!/usr/bin/env python3
"""Generic web crawler powered by optional Scrapling integration."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from crawlers.common.scrapling_adapter import extract_page_summary, fetch_page, get_status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrapling 通用网页采集")
    parser.add_argument("url", nargs="?", help="要采集的网页 URL")
    parser.add_argument("--max", dest="max_items", type=int, default=100, help="最大提取条数")
    parser.add_argument(
        "--mode",
        choices=["fetcher", "dynamic", "stealthy"],
        default="fetcher",
        help="Scrapling fetcher 模式",
    )
    return parser.parse_args()


def save_rows(summary: dict, url: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"scrapling_web_{timestamp}.csv"

    rows = []
    for heading in summary.get("headings", []):
        rows.append({"type": "heading", "title": summary.get("title", ""), "content": heading, "url": url, "href": ""})
    for paragraph in summary.get("paragraphs", []):
        rows.append({"type": "paragraph", "title": summary.get("title", ""), "content": paragraph, "url": url, "href": ""})
    for link in summary.get("links", []):
        rows.append({
            "type": "link",
            "title": summary.get("title", ""),
            "content": link.get("text", ""),
            "url": url,
            "href": link.get("href", ""),
        })

    if not rows and summary.get("text"):
        rows.append({"type": "text", "title": summary.get("title", ""), "content": summary["text"], "url": url, "href": ""})

    with output_file.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["type", "title", "content", "url", "href"])
        writer.writeheader()
        writer.writerows(rows)

    return output_file


def main() -> int:
    args = parse_args()
    if not args.url:
        print("请提供网页 URL，例如: python run.py https://example.com")
        return 2

    status = get_status()
    if not status.available:
        print(status.reason)
        return 1

    print("=" * 60)
    print("  Scrapling 通用网页采集")
    print("=" * 60)
    print(f"URL: {args.url}")
    print(f"模式: {args.mode}")
    print(f"最大条数: {args.max_items}")

    page = fetch_page(args.url, mode=args.mode)
    summary = extract_page_summary(page, max_items=args.max_items)

    output_file = save_rows(summary, args.url, Path("output"))
    print(f"标题: {summary.get('title') or '(未提取到标题)'}")
    print(f"标题/段落/链接: {len(summary.get('headings', []))}/{len(summary.get('paragraphs', []))}/{len(summary.get('links', []))}")
    print(f"输出文件: {output_file.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
