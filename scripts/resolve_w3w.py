#!/usr/bin/env python3
"""Resolve a what3words code to coordinates via the public og:image minimap URL.

The w3w page embeds the true square centre in the og:image minimap query
string (lat/lng), which is server-rendered and needs no JS/browser.
"""
from __future__ import annotations

import json
import re
import html
import sys
from urllib.parse import urlparse, parse_qs

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def resolve_w3w(code: str) -> dict:
    code = code.strip().lstrip("./").strip("/")
    url = f"https://what3words.com/{code}"
    r = requests.get(url, headers={"User-Agent": UA}, timeout=45)
    r.raise_for_status()
    m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', r.text)
    desc = re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"', r.text)
    out: dict = {"code": code, "http": r.status_code}
    if m:
        # og:image content has HTML-escaped (&amp;) entities; decode before parsing.
        img = html.unescape(m.group(1))
        out["ogImage"] = img
        q = parse_qs(urlparse(img).query)
        if "lat" in q and "lng" in q:
            out["lat"] = round(float(q["lat"][0]), 6)
            out["lng"] = round(float(q["lng"][0]), 6)
    if desc:
        out["description"] = desc.group(1)
    return out


if __name__ == "__main__":
    codes = sys.argv[1:] or ["strictest.torches.catch", "tablet.passwords.nowadays"]
    results = [resolve_w3w(c) for c in codes]
    print(json.dumps(results, indent=2, ensure_ascii=False))
