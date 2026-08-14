#!/usr/bin/env python3
"""Resolve a what3words code to coordinates AND address-verify it.

w3w squares are independent geographic points: the code tells you nothing about
a walk's *address*, so a copied, deduped (-2), or typo'd code can land miles from
the real meeting point. We therefore never accept a w3w coordinate blindly.

Verification strategy (defence in depth, all must pass):
  1. The resolved square must be inside the walk's country (country centroid
     isochrone check via a generous radius around the country's largest city /
     capital region). This catches the worst errors (wrong continent / country).
  2. Reverse-geocode the resolved lat/lng and confirm the walk's locality /
     region / country appears in the address. This catches wrong-city errors
     where the country is right but the town is wrong.
  3. If the official listing also publishes an Address / Meeting point string,
     require that its locality/region appears in the reverse-geocoded address.

Only if all applicable checks pass is the coordinate returned as 'confirmed'.
Otherwise it is returned as 'rejected' with reasons so a human can decide.

This module is safe to call offline for the country check (uses a small built-in
centroid table); the reverse-geocode check needs network (Nominatim).
"""
from __future__ import annotations

import html
import json
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse, parse_qs

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
# Nominatim requires a descriptive, identifying User-Agent (usage policy).
NOMINATIM_UA = "GGGW-Stats/0.1 (non-commercial community stats; source: greatglobalgreyhoundwalk.co.uk)"

# Approximate country reference points (capital / largest city) and a permissive
# acceptance radius in km. w3w squares that resolve outside this radius from the
# country reference are almost certainly wrong (wrong country / garbled code).
COUNTRY_REFERENCE = {
    "ar": (-34.6037, -58.3816, 3200),   # Argentina -> Buenos Aires
    "au": (-35.2809, 149.1300, 4000),   # Australia -> Canberra/Sydney wide
    "at": (48.2082, 16.3738, 400),      # Austria -> Vienna
    "be": (50.8503, 4.3517, 250),       # Belgium -> Brussels
    "bg": (42.6977, 23.3219, 400),      # Bulgaria -> Sofia
    "ca": (45.4215, -75.6972, 6000),    # Canada -> Ottawa wide
    "hr": (45.8150, 15.9819, 400),      # Croatia -> Zagreb
    "cz": (50.0755, 14.4378, 350),      # Czechia -> Prague
    "gb": (51.5074, -0.1278, 900),      # UK -> London (covers England/Scotland/Wales)
    "fr": (48.8566, 2.3522, 900),       # France -> Paris
    "de": (52.5200, 13.4050, 700),      # Germany -> Berlin
    "gi": (36.1408, -5.3536, 60),       # Gibraltar
    "gr": (37.9838, 23.7275, 500),      # Greece -> Athens
    "gg": (49.4583, -2.5806, 40),       # Guernsey
    "hu": (47.4979, 19.0402, 400),      # Hungary -> Budapest
    "ie": (53.3498, -6.2603, 300),      # Ireland -> Dublin
    "it": (41.9028, 12.4964, 800),      # Italy -> Rome
    "jp": (35.6762, 139.6503, 1200),    # Japan -> Tokyo
    "je": (49.2144, -2.1313, 40),       # Jersey
    "lu": (49.6116, 6.1296, 80),        # Luxembourg
    "mx": (19.4326, -99.1332, 3000),    # Mexico -> CDMX wide
    "nl": (52.3676, 4.9041, 300),       # Netherlands -> Amsterdam
    "nz": (-41.2865, 174.7762, 900),    # New Zealand -> Wellington
    "pt": (38.7223, -9.1393, 400),       # Portugal -> Lisbon
    "sm": (43.9354, 12.4578, 30),       # San Marino
    "za": (-25.7479, 28.2293, 1500),    # South Africa -> Pretoria wide
    "se": (59.3293, 18.0686, 900),      # Sweden -> Stockholm
    "ch": (46.9480, 7.4474, 300),       # Switzerland -> Bern
    "ae": (24.4539, 54.3773, 300),      # UAE -> Abu Dhabi
    "us": (38.9072, -77.0369, 5000),    # USA -> DC wide
    "sg": (1.3521, 103.8198, 60),       # Singapore
}

EXPECTED_COUNTRY_CODES = {
    "Argentina": "ar", "Australia": "au", "Austria": "at", "Belgium": "be", "Bulgaria": "bg", "Canada": "ca",
    "Croatia": "hr", "Croatia (Hrvatska)": "hr", "Czech Republic": "cz", "England": "gb", "France": "fr", "Germany": "de", "Gibraltar": "gi",
    "Greece": "gr", "Guernsey": "gg", "Hungary": "hu", "Ireland": "ie", "Italy": "it", "Japan": "jp",
    "Jersey": "je", "Luxembourg": "lu", "Mexico": "mx", "Netherlands": "nl", "New Zealand": "nz", "Portugal": "pt", "San Marino": "sm",
    "Scotland": "gb", "Singapore": "sg", "South Africa": "za", "Sweden": "se", "Switzerland": "ch", "United Arab Emirates": "ae",
    "United States": "us", "Wales": "gb",
}

NOMINATIM = "https://nominatim.openstreetmap.org/reverse"


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    from math import radians, sin, cos, asin, sqrt
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * r * asin(sqrt(a))


def normalise_w3w(value: str) -> str:
    return ".".join(re.findall(r"\w+", value)).casefold()


W3W_WORDS_RE = re.compile(r"[\w\u00C0-\uFFFF]+\.[\w\u00C0-\uFFFF]+\.[\w\u00C0-\uFFFF]+")


def extract_w3w_words(value: str) -> str:
    """Return the dotted three-word code from a w3w field (handles ///code, URL, slash forms)."""
    m = W3W_WORDS_RE.search(value or "")
    return m.group(0).casefold() if m else ""


def resolve_w3w_coords(code: str) -> tuple[float, float, str]:
    """Return (lat, lng, description) from the w3w og:image minimap."""
    code = code.strip().lstrip("./").strip("/")
    url = f"https://what3words.com/{code}"
    r = requests.get(url, headers={"User-Agent": UA}, timeout=45)
    r.raise_for_status()
    m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', r.text)
    desc = re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"', r.text)
    if not m:
        raise ValueError(f"Could not find og:image for {code}")
    # og:image content carries HTML-escaped entities (&amp;); decode before parsing.
    img_url = html.unescape(m.group(1))
    q = parse_qs(urlparse(img_url).query)
    if "lat" not in q or "lng" not in q:
        raise ValueError(f"No lat/lng in og:image for {code}")
    return round(float(q["lat"][0]), 6), round(float(q["lng"][0]), 6), (desc.group(1) if desc else "")


def reverse_geocode(lat: float, lng: float) -> dict[str, Any]:
    """Reverse-geocode via Nominatim; returns address dict + display_name."""
    resp = requests.get(NOMINATIM, params={"lat": lat, "lon": lng, "format": "jsonv2", "addressdetails": 1},
                        headers={"User-Agent": NOMINATIM_UA}, timeout=45)
    resp.raise_for_status()
    data = resp.json()
    return {"display_name": data.get("display_name", ""), "address": data.get("address", {})}


@dataclass
class W3WVerification:
    code: str
    lat: float
    lng: float
    status: str = "rejected"          # 'confirmed' | 'rejected' | 'unverified'
    reasons: list[str] = field(default_factory=list)
    display_name: str = ""
    country_code: str = ""


def verify_w3w_against_walk(code: str, walk: dict[str, Any], reverse_geocode_enabled: bool = True) -> W3WVerification:
    """Resolve `code` and verify it agrees with the walk's address details."""
    clean = normalise_w3w(code)
    lat, lng, desc = resolve_w3w_coords(clean)
    ver = W3WVerification(code=clean, lat=lat, lng=lng)

    # The listing's own w3w (if present) must match what we resolved. Extract the
    # three-word code from URL/slash/dotted forms so the comparison is apples-to-apples.
    listing_words = extract_w3w_words(walk.get("what3words") or "")
    if listing_words and listing_words != clean:
        ver.reasons.append(
            f"Code '{clean}' does not match the listing's own w3w '{listing_words}'"
        )

    # 1) Country agreement via reference radius.
    cc = EXPECTED_COUNTRY_CODES.get(walk.get("country", ""))
    if cc and cc in COUNTRY_REFERENCE:
        ref_lat, ref_lng, radius = COUNTRY_REFERENCE[cc]
        dist = _haversine_km(lat, lng, ref_lat, ref_lng)
        ver.country_code = cc
        if dist > radius:
            ver.reasons.append(
                f"Resolved point is {dist:.0f} km from {cc} reference (limit {radius} km)"
            )
    elif cc is None:
        ver.reasons.append(f"No reference point for country '{walk.get('country')}'")

    # 2) Reverse-geocode agreement with walk locality/region/country.
    if reverse_geocode_enabled:
        try:
            rg = reverse_geocode(lat, lng)
            ver.display_name = rg["display_name"]
            addr = rg.get("address", {})
            ver.country_code = addr.get("country_code", ver.country_code)
            haystack = " ".join(
                str(v) for v in (rg["display_name"], *(addr.values()))
            ).casefold()
            locality = (walk.get("locality") or "").casefold()
            region = (walk.get("region") or "").casefold()
            country = (walk.get("country") or "").casefold()
            checks = [("country", country), ("region", region), ("locality", locality)]
            matched = [name for name, val in checks if val and val in haystack]
            missing = [name for name, val in checks if val and val not in haystack]
            if country and country not in haystack:
                ver.reasons.append(f"Reverse-geocoded address missing walk country '{walk.get('country')}'")
            if missing:
                ver.reasons.append(
                    f"Reverse-geocoded address does not mention walk {', '.join(missing)} "
                    f"('{walk.get('locality')}', '{walk.get('region')}')"
                )
            # 3) Listing address / meeting-point locality should also appear.
            for field_name in ("address", "meetingPoint"):
                val = (walk.get(field_name) or "").casefold()
                if val:
                    # use the most distinctive token (>=4 chars, alphabetic)
                    tokens = [t for t in re.split(r"[^a-z0-9]+", val) if len(t) >= 4]
                    if tokens and not any(t in haystack for t in tokens):
                        ver.reasons.append(
                            f"Listing {field_name} token(s) {tokens[:3]} not found near resolved point"
                        )
                        break
        except Exception as exc:  # network/reverse failure -> do not confirm
            ver.reasons.append(f"Reverse-geocode failed: {exc}")

    if not ver.reasons:
        ver.status = "confirmed"
    return ver


if __name__ == "__main__":
    # CLI: resolve + verify a code against a walk passed as JSON on stdin,
    # or just resolve if no walk is given.
    raw = sys.stdin.read().strip()
    if raw:
        payload = json.loads(raw)
        code = payload["code"]
        walk = payload.get("walk", {})
        ver = verify_w3w_against_walk(code, walk)
        print(json.dumps(ver.__dict__, indent=2, ensure_ascii=False))
    else:
        for c in sys.argv[1:]:
            lat, lng, desc = resolve_w3w_coords(c)
            print(f"{c} -> {lat}, {lng}  ({desc})")
