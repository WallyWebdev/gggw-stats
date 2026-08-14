#!/usr/bin/env python3
"""Targeted import of newly-discovered walks into the existing dataset.

Unlike scrape_walks.py (which re-fetches the entire schedule), this only
fetches the walk IDs passed on the command line, geocodes them, and merges
them into the current src/data/walks.json. Every existing walk's data and
pin is preserved untouched.

Usage:
    python scripts/import_new_walks.py <id1> <id2> ...
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from w3w_verify import verify_w3w_against_walk

ROOT = Path(__file__).resolve().parents[1]
WALKS_JSON = ROOT / "src" / "data" / "walks.json"
VERIFIED_LOCATIONS_FILE = ROOT / "scripts" / "verified-locations.json"
CACHE = ROOT / ".cache" / "geocodes.json"

USER_AGENT = "GGGW-Stats/0.1 (non-commercial community stats; source: greatglobalgreyhoundwalk.co.uk)"
NOMINATIM_UA = "GGGW-Stats/0.1 (non-commercial community stats; source: greatglobalgreyhoundwalk.co.uk)"

EXPECTED_COUNTRY_CODES = {
    "Argentina": "ar", "Australia": "au", "Austria": "at", "Belgium": "be", "Bulgaria": "bg", "Canada": "ca",
    "Croatia": "hr", "Croatia (Hrvatska)": "hr", "Czech Republic": "cz", "England": "gb", "France": "fr", "Germany": "de", "Gibraltar": "gi",
    "Greece": "gr", "Guernsey": "gg", "Hungary": "hu", "Ireland": "ie", "Italy": "it", "Japan": "jp",
    "Jersey": "je", "Luxembourg": "lu", "Mexico": "mx", "Netherlands": "nl", "New Zealand": "nz", "Portugal": "pt", "San Marino": "sm",
    "Scotland": "gb", "Singapore": "sg", "South Africa": "za", "Sweden": "se", "Switzerland": "ch", "United Arab Emirates": "ae",
    "United States": "us", "Wales": "gb",
}


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def get(session: requests.Session, url: str, retries: int = 4) -> requests.Response:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            resp = session.get(url, timeout=45)
            resp.raise_for_status()
            return resp
        except Exception as exc:  # transient resets/5xx -> retry with backoff
            last = exc
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    raise last


def parse_walk(session: requests.Session, url: str) -> dict:
    soup = BeautifulSoup(get(session, url).text, "html.parser")
    heading = soup.select_one("h1")
    title = clean(heading.get_text(" ", strip=True))
    fields: dict[str, str] = {}
    for row in soup.select("table tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) < 2:
            continue
        key = clean(cells[0].get_text(" ", strip=True)).rstrip(":")
        value = clean(cells[1].get_text(" ", strip=True))
        if key and value and key not in fields:
            fields[key] = value
    parts = [clean(p) for p in title.split(",") if clean(p)]
    country = parts[0] if parts else "Unknown"
    locality = parts[-1] if len(parts) > 1 else country
    region = ", ".join(parts[1:-1]) if len(parts) > 2 else ""
    return {
        "id": url.rstrip("/").rsplit("/", 1)[-1],
        "title": title, "country": country, "region": region, "locality": locality,
        "address": fields.get("Address", ""),
        "postcode": fields.get("Postcode", fields.get("Nearest Postcode", "")),
        "what3words": fields.get("What 3 Words", ""),
        "walkType": fields.get("Type of Walk", fields.get("Type Of Walk", "")),
        "startTime": fields.get("Start time", fields.get("Start Time", "")),
        "duration": fields.get("Duration", ""),
        "meetingPoint": fields.get("Meeting point", ""),
        "parking": fields.get("Parking", ""),
        "organiser": fields.get("Organiser", fields.get("Rescue / Organisation / Walking Group Name", "")),
        "leader": fields.get("Walk Leader Name", fields.get("Contact", "")),
        "shortWalk": fields.get("Short Walk Available", ""),
        "refreshments": fields.get("Cafe or refreshments Available", ""),
        "accessible": fields.get("Suitable for Buggies & Wheelchairs", ""),
        "toilets": fields.get("Toilet facilities", ""),
        "info": fields.get("Additional Information", fields.get("Info", "")),
        "organiserUrl": fields.get("Organiser Website", ""),
        "sourceUrl": url,
    }


def query_candidates(walk: dict) -> list[str]:
    country = walk["country"]
    candidates = [
        ", ".join(filter(None, [walk["address"], walk["postcode"], country])),
        ", ".join(filter(None, [walk["meetingPoint"], country])),
        ", ".join(filter(None, [walk["locality"], walk["region"], walk["postcode"], country])),
        ", ".join(filter(None, [walk["postcode"], country])),
        ", ".join(filter(None, [walk["locality"], walk["region"], country])),
        walk["title"],
    ]
    cleaned = []
    for item in candidates:
        c = clean(item)
        if not c:
            continue
        if "http" in c.lower() or len(c) > 120:
            continue
        cleaned.append(c)
    return list(dict.fromkeys(cleaned))


def geocode(session: requests.Session, walk: dict, cache: dict, confirmed: dict) -> dict | None:
    coords = re.search(r"(?<!\\d)(-?\\d{1,2}\\.\\d+)\\s*,\\s*(-?\\d{1,3}\\.\\d+)(?!\\d)", walk["meetingPoint"])
    if coords:
        return {"lat": round(float(coords.group(1)), 6), "lng": round(float(coords.group(2)), 6),
                "displayName": walk["meetingPoint"], "query": walk["meetingPoint"],
                "precision": "published coordinates", "provider": "Official GGGW listing", "verificationUrl": walk["sourceUrl"]}
    if walk["id"] in confirmed:
        return confirmed[walk["id"]]
    exp = EXPECTED_COUNTRY_CODES.get(walk["country"])
    cached = cache.get(walk["id"])
    if cached and cached.get("query") in query_candidates(walk) and cached.get("countryCode") == exp:
        return cached
    for q in query_candidates(walk):
        try:
            resp = session.get("https://nominatim.openstreetmap.org/search",
                               params={"q": q, "format": "jsonv2", "limit": 1, "addressdetails": 1},
                               headers={"User-Agent": NOMINATIM_UA}, timeout=45)
            resp.raise_for_status()
            results = resp.json()
        except Exception:
            results = []
        time.sleep(1.05)
        if results:
            r = results[0]
            cc = r.get("address", {}).get("country_code")
            if exp and cc != exp:
                continue
            value = {"lat": round(float(r["lat"]), 6), "lng": round(float(r["lon"]), 6),
                     "displayName": r.get("display_name", ""), "query": q,
                     "precision": "address" if walk["address"] and q.startswith(walk["address"]) else "locality",
                     "countryCode": cc, "provider": "OpenStreetMap Nominatim"}
            cache[walk["id"]] = value
            return value
    cache[walk["id"]] = None
    return None


W3W_RE = re.compile(
    r"(?:///|w3w\.co/|www\.what3words\.com/)?"
    r"([\w\u00C0-\uFFFF]+\.[\w\u00C0-\uFFFF]+\.[\w\u00C0-\uFFFF]+)"
)


def classify_w3w(walk: dict) -> tuple[str, object]:
    """Return ('none', None) | ('confirmed', loc) | ('rejected', reasons) | ('error', reason)."""
    raw = (walk.get("what3words") or "").strip()
    m = W3W_RE.search(raw)
    if not m:
        return "none", None
    code = m.group(1)
    try:
        ver = verify_w3w_against_walk(code, walk, reverse_geocode_enabled=True)
    except Exception as exc:  # resolution/network failure -> never confirm
        return "error", str(exc)
    if ver.status == "confirmed":
        loc = {
            "lat": ver.lat,
            "lng": ver.lng,
            "displayName": ver.display_name or walk["title"],
            "query": "///" + ver.code,
            "precision": "exact meeting point",
            "sourceType": "what3words",
            "what3words": "///" + ver.code,
            "accuracy": "three-metre square",
            "coordinateStatus": "confirmed",
            "provider": "What3Words resolution + reverse-geocode verification",
        }
        return "confirmed", loc
    return "rejected", "; ".join(ver.reasons)


def main() -> int:
    ids = sys.argv[1:]
    if not ids:
        print("Usage: import_new_walks.py <id> [<id> ...]")
        return 2
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    data = json.loads(WALKS_JSON.read_text())
    existing = {w["id"]: w for w in data["walks"]}
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    confirmed = json.loads(VERIFIED_LOCATIONS_FILE.read_text()) if VERIFIED_LOCATIONS_FILE.exists() else {}

    added = []
    flags = []
    new_confirmed = {}
    for wid in ids:
        if wid in existing:
            print(f"skip (already present): {wid}")
            continue
        url = f"https://greatglobalgreyhoundwalk.co.uk/walks/{wid}/"
        walk = parse_walk(session, url)
        state, payload = classify_w3w(walk)
        if state == "confirmed":
            loc = payload
            new_confirmed[wid] = loc
            print(f"+ {walk['title']}: w3w CONFIRMED {loc['lat']},{loc['lng']} ({loc['what3words']})")
        else:
            if state != "none":
                flags.append(f"{wid}: w3w {state} ({payload}); falling back to Nominatim")
                print(f"  ! {wid}: w3w {state}: {payload}")
            loc = geocode(session, walk, cache, confirmed)
            if loc is None:
                flags.append(f"{wid}: UNMAPPED (no coordinate found)")
                print(f"+ {walk['title']}: UNMAPPED")
            else:
                print(f"+ {walk['title']}: {loc['lat']},{loc['lng']} ({loc.get('precision')})")
        walk["location"] = loc
        data["walks"].append(walk)
        added.append(walk)

    if not added:
        print("Nothing to import.")
        return 0

    if new_confirmed:
        merged = dict(confirmed)
        overlap = [k for k in new_confirmed if k in merged]
        assert not overlap, f"Refusing to overwrite existing confirmed pins: {overlap}"
        merged.update(new_confirmed)
        VERIFIED_LOCATIONS_FILE.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n")
        print(f"Updated {VERIFIED_LOCATIONS_FILE} with {len(new_confirmed)} confirmed w3w pin(s)")

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n")

    countries = Counter(w["country"] for w in data["walks"])
    data["meta"] = {
        "sourceUrl": data["meta"]["sourceUrl"],
        "eventDate": data["meta"]["eventDate"],
        "scrapedAt": datetime.now(timezone.utc).isoformat(),
        "walkCount": len(data["walks"]),
        "mappedCount": sum(bool(w.get("location")) for w in data["walks"]),
        "countryCount": len(countries),
    }
    data["countries"] = [{"country": c, "count": n} for c, n in sorted(countries.items(), key=lambda i: (-i[1], i[0]))]
    WALKS_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"\nWrote {WALKS_JSON}: {data['meta']['walkCount']} walks, {data['meta']['mappedCount']} mapped, {data['meta']['countryCount']} countries")
    print(f"Added {len(added)} new walks.")
    if flags:
        print("\nFLAGS:")
        for f in flags:
            print(f"  - {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
