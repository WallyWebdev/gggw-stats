#!/usr/bin/env python3
"""Fetch GGGW walk detail pages via browser and cache their HTML.

Usage:
    python scripts/fetch_walk_pages.py <id1> <id2> ...

Writes HTML to .cache/walk-pages/<id>.html
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

# Import the browser fetch helper
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gggw_browser import fetch_html

SOURCE_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = SOURCE_ROOT / ".cache" / "walk-pages"
SOURCE_URL = "https://greatglobalgreyhoundwalk.co.uk/walk-schedule/"


def live_ids() -> set[str]:
    """Fetch the schedule index and extract all walk slugs."""
    html = fetch_html(SOURCE_URL)
    soup = BeautifulSoup(html, "html.parser")
    ids = set()
    for anchor in soup.select('a[href*="/walks/"]'):
        href = anchor.get("href", "").split("#", 1)[0]
        m = re.search(r"/walks/([^/]+)/$", href)
        if m:
            ids.add(m.group(1))
    return ids


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print("Usage: fetch_walk_pages.py <id1> <id2> ...")
        return 2

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    for wid in args:
        outfile = CACHE_DIR / f"{wid}.html"
        if outfile.exists():
            print(f"skip (cached): {wid}")
            continue
        url = f"https://greatglobalgreyhoundwalk.co.uk/walks/{wid}/"
        print(f"fetch: {wid}")
        try:
            html = fetch_html(url)
            outfile.write_text(html)
            print(f"  saved {len(html)} chars")
        except Exception as exc:
            print(f"  ERROR: {exc}")
            # Write an error marker so we don't retry endlessly
            outfile.write_text(f"__FETCH_FAILED__: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
