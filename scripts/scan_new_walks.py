#!/usr/bin/env python3
"""Non-destructive scan: compare live GGGW schedule IDs against local walks.json.

Reports added/removed walk IDs and writes a machine-readable diff JSON.
Never writes src/data/walks.json.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from gggw_browser import fetch_html

SOURCE_URL = "https://greatglobalgreyhoundwalk.co.uk/walk-schedule/"
ROOT = Path(__file__).resolve().parents[1]
WALKS_JSON = ROOT / "src" / "data" / "walks.json"
DIFF_OUT = ROOT / ".cache" / "scan-diff.json"


def live_ids() -> set[str]:
    # Use the browser-based fetcher to bypass SiteGround's /sgcaptcha/ WAF,
    # which serves an HTTP 200 JS-challenge wall to non-browser clients.
    html = fetch_html(SOURCE_URL)
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    for anchor in soup.select('a[href*="/walks/"]'):
        href = anchor.get("href", "").split("#", 1)[0]
        if re.fullmatch(r"https://greatglobalgreyhoundwalk\.co\.uk/walks/[^/]+/", href) and href not in urls:
            urls.append(href)
    return {u.rstrip("/").rsplit("/", 1)[-1] for u in urls}


def load_local() -> dict[str, dict]:
    data = json.loads(WALKS_JSON.read_text())
    return {w["id"]: w for w in data["walks"]}


def main() -> int:
    print(f"Scanning {SOURCE_URL} ...")
    live = live_ids()
    print(f"Live listings: {len(live)}")
    local = load_local()
    print(f"Local walks:   {len(local)}")

    added = sorted(live - local.keys())
    removed = sorted(local.keys() - live)

    diff = {
        "liveCount": len(live),
        "localCount": len(local),
        "addedCount": len(added),
        "removedCount": len(removed),
        "added": added,
        "removed": removed,
    }
    DIFF_OUT.parent.mkdir(parents=True, exist_ok=True)
    DIFF_OUT.write_text(json.dumps(diff, indent=2) + "\n")
    print(f"Wrote {DIFF_OUT}")

    if added:
        print(f"\nNEW WALKS ({len(added)}):")
        for wid in added:
            print(f"  + {wid}")
    else:
        print("\nNo new walks.")
    if removed:
        print(f"\nREMOVED ({len(removed)}):")
        for wid in removed:
            print(f"  - {wid}  ({local[wid]['title']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
