#!/usr/bin/env python3
"""Browser-based fetcher for GGGW pages.

The GGGW site is hosted on SiteGround (NOT Cloudflare).  SiteGround's WAF
serves an HTTP 200 /sgcaptcha/ JS-challenge wall to non-browser clients
(urllib, requests with a fake UA).  Every parsed field comes back empty,
so a diff looks like "all 289 records diverged" — a false positive.

Real browsers (Chrome via the browser_exec harness) execute the challenge
and return clean data.  This module provides a single ``fetch_html`` that
uses a persistent browser session, plus a fallback ``requests`` path that
slows down and sets a realistic browser UA + Referer + cookie jar (useful
only when the browser is unavailable).

Usage from any script:
    from gggw_browser import fetch_html
    html = fetch_html("https://greatglobalgreyhoundwalk.co.uk/walk-schedule/")
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
REFERER = "https://greatglobalgreyhoundwalk.co.uk/walk-schedule/"


def _fetch_with_browser(url: str, timeout_s: int = 120) -> str | None:
    """Fetch page HTML via the browser_exec harness (real Chrome).

    Returns the HTML string, or None if the browser is unavailable / fails.
    """
    script = f"""
from browser_harness.helpers import js, new_tab, wait_for_load
import time

new_tab({url!r})
wait_for_load()
# Give SPA-like content time to render
time.sleep(2)
try:
    html = js('document.documentElement.outerHTML')
except Exception:
    html = ''
print('LEN:' + str(len(html)))
if html and len(html) > 100:
    import textwrap
    # Print in chunks to avoid CDP payload limits
    chunk_size = 80000
    for i in range(0, len(html), chunk_size):
        print('CHUNK:' + html[i:i+chunk_size])
else:
    print('FAIL: empty or tiny response')
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=str(SOURCE_ROOT),
        )
        output = result.stdout
        lines = output.split("\n")
        status_line = lines[0] if lines else ""
        if "FAIL" in status_line:
            return None
        chunks = [l for l in lines if l.startswith("CHUNK:")]
        if chunks:
            return "".join(c[6:] for c in chunks)
        # Fallback: single large line
        return output[len("LEN:"):].strip() if output.startswith("LEN:") else None
    except (subprocess.TimeoutExpired, Exception):
        return None


def _fetch_with_requests(url: str) -> str | None:
    """Fallback: requests with a browser-like UA + referer + throttling.

    Only works if the WAF challenge is lenient.  Returns None on failure.
    """
    try:
        import requests

        session = requests.Session()
        session.headers.update({
            "User-Agent": USER_AGENT,
            "Referer": REFERER,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        })
        # Seed a cookie jar to look more browser-like
        session.get("https://greatglobalgreyhoundwalk.co.uk/walk-schedule/", timeout=30)
        time.sleep(1.5)

        resp = session.get(url, timeout=45)
        if "/sgcaptcha/" in resp.url or "sgcaptcha" in resp.text.lower():
            return None  # WAF challenge hit
        return resp.text
    except Exception:
        return None


def fetch_html(url: str, timeout_s: int = 120) -> str:
    """Fetch HTML from a GGGW page, bypassing the SiteGround WAF.

    Tries the browser first (reliable), then falls back to requests with
    a realistic UA.  Raises RuntimeError if both fail.
    """
    # Try browser first
    html = _fetch_with_browser(url, timeout_s)
    if html and len(html) > 1000 and "sgcaptcha" not in html.lower():
        return html

    # Fallback to requests
    html = _fetch_with_requests(url)
    if html and len(html) > 1000 and "sgcaptcha" not in html.lower():
        return html

    raise RuntimeError(
        f"Failed to fetch {url} — both browser and requests paths hit "
        f"the SiteGround /sgcaptcha/ WAF challenge or returned empty content."
    )
