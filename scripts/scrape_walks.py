#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://greatglobalgreyhoundwalk.co.uk/walk-schedule/"
USER_AGENT = "GGGW-Stats/0.1 (non-commercial community stats prototype; source: greatglobalgreyhoundwalk.co.uk)"
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "src" / "data" / "walks.json"
CACHE = ROOT / ".cache" / "geocodes.json"
VERIFIED_LOCATIONS_FILE = ROOT / "scripts" / "verified-locations.json"
EXPECTED_COUNTRY_CODES = {
    "Argentina": "ar", "Australia": "au", "Austria": "at", "Belgium": "be", "Bulgaria": "bg", "Canada": "ca",
    "Croatia": "hr", "Croatia (Hrvatska)": "hr", "Czech Republic": "cz", "England": "gb", "France": "fr", "Germany": "de", "Gibraltar": "gi",
    "Greece": "gr", "Guernsey": "gg", "Hungary": "hu", "Ireland": "ie", "Italy": "it", "Japan": "jp",
    "Jersey": "je", "Luxembourg": "lu", "Mexico": "mx", "Netherlands": "nl", "New Zealand": "nz", "Portugal": "pt", "San Marino": "sm",
    "Scotland": "gb", "South Africa": "za", "Sweden": "se", "Switzerland": "ch", "United Arab Emirates": "ae",
    "United States": "us", "Wales": "gb",
}
MANUAL_LOCATIONS = {
    "jersey-st-lawrence-and-st-peter-st-helier": {
        "lat": 49.190372,
        "lng": -2.119226,
        "displayName": "West Park, St Helier, Jersey",
        "query": "West Park, St Helier, Jersey",
        "precision": "published meeting point",
        "verificationUrl": "https://greatglobalgreyhoundwalk.co.uk/walks/jersey-st-lawrence-and-st-peter-st-helier/",
    },
    "wales-conway-llanfairfechan": {
        "lat": 53.25992,
        "lng": -3.97594,
        "displayName": "Llanfairfechan Promenade, near Pavilion Cafe, Wales",
        "query": "Llanfairfechan Promenade, Wales",
        "precision": "published meeting area",
        "verificationUrl": "https://greatglobalgreyhoundwalk.co.uk/walks/wales-conway-llanfairfechan/",
    },
    "england-cheshire-stalybridge": {
        "lat": 53.478371,
        "lng": -2.049595,
        "displayName": "Cheetham Park, Stalybridge, England",
        "query": "Cheetham Park, 33 Acres Lane, Stalybridge, SK15 2JR",
        "precision": "published venue",
        "verificationUrl": "https://mapcarta.com/W369652530",
    },
    "england-county-durham-eaglescliffe": {
        "lat": 54.536,
        "lng": -1.337,
        "displayName": "Preston Park Museum & Grounds, Eaglescliffe, England",
        "query": "Preston Park Museum, Yarm Road, Eaglescliffe, TS18 3RH",
        "precision": "published meeting point",
        "verificationUrl": "https://www.prestonparkmuseum.co.uk/",
    },
    "guernsey-pembroke": {
        "lat": 49.50313,
        "lng": -2.53241,
        "displayName": "The Beach House, Pembroke Bay, Guernsey",
        "query": "The Beach House, Pembroke Bay, Guernsey, GY3 5BY",
        "precision": "published meeting point",
        "verificationUrl": "https://gg.geoview.info/beach_house,2512820952n",
    },
    "sweden-bohuslan-uddevalla": {
        "lat": 58.329717,
        "lng": 11.90645,
        "displayName": "Bodelefälten, Gustavsberg, Uddevalla, Sweden",
        "query": "Bodelefälten, Gustavsberg 306, 451 91 Uddevalla",
        "precision": "published meeting point",
        "verificationUrl": "https://www.uddevalla.se/uppleva-och-gora/idrott-motion-och-friluftsliv/hallar-och-idrottsanlaggningar/bodelefalten.html",
    },
    "australia-south-australia-adelaide-wynne-vale-dam": {
        "lat": -34.799341,
        "lng": 138.700651,
        "displayName": "Wynn Vale Dam, Wynn Vale, South Australia",
        "query": "Wynn Vale Dam, South Australia",
        "precision": "published venue",
        "verificationUrl": "https://www.teatreegully.sa.gov.au/community-and-recreation/parks-playgrounds-and-ovals/wynn-vale-dam",
    },
    "czech-republic-liberec-jablonneho-v-podjestedi": {
        "lat": 50.777497,
        "lng": 14.788104,
        "displayName": "Zámek Lemberk, Jablonné v Podještědí, Czechia",
        "query": "Lemberk Castle, Lvová 1, 47125 Jablonné v Podještědí",
        "precision": "published venue",
        "verificationUrl": "https://www.zamek-lemberk.cz/en",
    },
    "england-cheshire-glazebury": {
        "lat": 53.476051,
        "lng": -2.497155,
        "displayName": "Bents Garden Centre, Warrington Road, Glazebury",
        "query": "Bents Garden Centre, Warrington Road, Glazebury",
        "precision": "published meeting point",
        "verificationUrl": "https://www.bents.co.uk/",
    },
    "australia-queensland-benowa-gold-coast-qld": {
        "lat": -28.009243,
        "lng": 153.388008,
        "displayName": "Gold Coast Regional Botanic Gardens, Benowa, Queensland",
        "query": "Gold Coast Regional Botanic Gardens, Ashmore Road, Benowa",
        "precision": "published meeting point",
        "verificationUrl": "https://toiletmap.gov.au/10279",
    },
    "australia-queensland-cairns": {
        "lat": -16.914733,
        "lng": 145.772522,
        "displayName": "Muddy's Playground, Cairns Esplanade, Queensland",
        "query": "Muddy's Playground, 174 Esplanade, Cairns",
        "precision": "published meeting point",
        "verificationUrl": "https://toiletmap.gov.au/49251",
    },
    "england-staffordshire-stoke-on-trent": {
        "lat": 53.000329,
        "lng": -2.106948,
        "displayName": "Park Hall Country Park, Bolton Gate, Stoke-on-Trent",
        "query": "Park Hall Country Park, Bolton Gate, ST3 6QD",
        "precision": "published meeting point",
        "verificationUrl": "https://www.waze.com/live-map/directions/gb/england/park-hall-country-park-(bolton-gate)?to=place.ChIJu388hzhqekgRLsqkUdJpHm8",
    },
    "germany-hamburg": {
        "lat": 53.573972,
        "lng": 10.002262,
        "displayName": "AlsterCliff, Fährdamm 13, Hamburg",
        "query": "AlsterCliff, Fährdamm 13, 20148 Hamburg",
        "precision": "published meeting point",
        "verificationUrl": "https://www.hamburg-travel.com/shopping-enjoying/restaurants-cafes/alstercliff-1/",
    },
    "italy-lombardy-milano": {
        "lat": 45.501682,
        "lng": 9.233977,
        "displayName": "NAMA Nuovo Anfiteatro Martesana, Milano",
        "query": "Via Agordat 19A, 20127 Milano",
        "precision": "published venue",
        "verificationUrl": "https://www.nuovoanfiteatromartesana.org/en/about-2/",
    },
    "japan-okinawa-nakagami-district": {
        "lat": 26.441037,
        "lng": 127.713749,
        "displayName": "Cape Zanpa Lighthouse, Yomitan, Okinawa",
        "query": "Cape Zanpa Lighthouse, Okinawa 904-0328",
        "precision": "published venue",
        "verificationUrl": "https://okinawa.stripes.com/travel/video-exploring-okinawa-quick-trip-to-scenic-cape-zanpa.html",
    },
    "united-states-missouri-saint-louis-forest-park": {
        "lat": 38.6408,
        "lng": -90.2807,
        "displayName": "The Muny, 1 Theatre Drive, St. Louis",
        "query": "The Muny, 1 Theatre Drive, St. Louis, MO 63112",
        "precision": "published meeting point",
        "verificationUrl": "https://www.lewisandclark.travel/listing/the-muny/",
    },
    "sweden-uppland-solna": {
        "lat": 59.353491,
        "lng": 18.039839,
        "displayName": "Haga tingshus, 12 Annerovägen, Solna, Sweden",
        "query": "Annerovägen 12, 16970 Solna, Sweden",
        "precision": "published meeting point",
        "verificationUrl": "https://greatglobalgreyhoundwalk.co.uk/walks/sweden-uppland-solna/",
    },
    "switzerland-zurich-hongg-trinkbrunnen-zurich": {
        "lat": 47.400813,
        "lng": 8.517188,
        "displayName": "Trinkbrunnen, Höngg, Zürich, Switzerland",
        "query": "Trinkbrunnen, Höngg, 8037 Zürich",
        "precision": "published meeting point",
        "verificationUrl": "https://www.google.com/maps?q=Trinkbrunnen,+H%C3%B6ngg,+8037+Z%C3%BCrich&ftid=0x47900b72a46c7d6f:0x7b5a10bf19436672&entry=gps",
    },
}


def verified_locations() -> dict[str, dict[str, Any]]:
    """Load durable, human-confirmed locations before any automated geocoding."""
    if not VERIFIED_LOCATIONS_FILE.exists():
        return {}
    locations = json.loads(VERIFIED_LOCATIONS_FILE.read_text())
    if not isinstance(locations, dict):
        raise ValueError(f"{VERIFIED_LOCATIONS_FILE} must contain an object keyed by walk ID")
    return locations


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def get(session: requests.Session, url: str) -> requests.Response:
    response = session.get(url, timeout=45)
    response.raise_for_status()
    return response


def listing_urls(session: requests.Session) -> list[str]:
    soup = BeautifulSoup(get(session, SOURCE_URL).text, "html.parser")
    urls: list[str] = []
    for anchor in soup.select('a[href*="/walks/"]'):
        href = anchor.get("href", "").split("#", 1)[0]
        if re.fullmatch(r"https://greatglobalgreyhoundwalk\.co\.uk/walks/[^/]+/", href) and href not in urls:
            urls.append(href)
    return urls


def parse_walk(session: requests.Session, url: str) -> dict[str, Any]:
    soup = BeautifulSoup(get(session, url).text, "html.parser")
    heading = soup.select_one("h1")
    if not heading:
        raise ValueError(f"No h1 found at {url}")
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

    location_parts = [clean(part) for part in title.split(",") if clean(part)]
    country = location_parts[0] if location_parts else "Unknown"
    locality = location_parts[-1] if len(location_parts) > 1 else country
    region = ", ".join(location_parts[1:-1]) if len(location_parts) > 2 else ""

    return {
        "id": url.rstrip("/").rsplit("/", 1)[-1],
        "title": title,
        "country": country,
        "region": region,
        "locality": locality,
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


def query_candidates(walk: dict[str, Any]) -> list[str]:
    country = walk["country"]
    candidates = [
        ", ".join(filter(None, [walk["address"], walk["postcode"], country])),
        ", ".join(filter(None, [walk["meetingPoint"], country])),
        ", ".join(filter(None, [walk["locality"], walk["region"], walk["postcode"], country])),
        ", ".join(filter(None, [walk["locality"], walk["region"], country])),
        walk["title"],
    ]
    return list(dict.fromkeys(clean(item) for item in candidates if clean(item)))


def geocode(
    session: requests.Session,
    walk: dict[str, Any],
    cache: dict[str, Any],
    confirmed_locations: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    coordinates = re.search(r"(?<!\d)(-?\d{1,2}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)(?!\d)", walk["meetingPoint"])
    if coordinates:
        return {
            "lat": round(float(coordinates.group(1)), 6),
            "lng": round(float(coordinates.group(2)), 6),
            "displayName": walk["meetingPoint"],
            "query": walk["meetingPoint"],
            "precision": "published coordinates",
            "provider": "Official GGGW listing",
            "verificationUrl": walk["sourceUrl"],
        }
    if walk["id"] in confirmed_locations:
        return confirmed_locations[walk["id"]]
    if walk["id"] in MANUAL_LOCATIONS:
        return MANUAL_LOCATIONS[walk["id"]]
    expected_country_code = EXPECTED_COUNTRY_CODES.get(walk["country"])
    cached = cache.get(walk["id"])
    if (
        cached
        and cached.get("query") in query_candidates(walk)
        and cached.get("countryCode") == expected_country_code
    ):
        return cached
    for query in query_candidates(walk):
        response = session.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "jsonv2", "limit": 1, "addressdetails": 1},
            timeout=45,
        )
        response.raise_for_status()
        results = response.json()
        time.sleep(1.05)
        if results:
            result = results[0]
            country_code = result.get("address", {}).get("country_code")
            if expected_country_code and country_code != expected_country_code:
                continue
            value = {
                "lat": round(float(result["lat"]), 6),
                "lng": round(float(result["lon"]), 6),
                "displayName": result.get("display_name", ""),
                "query": query,
                "precision": "address" if walk["address"] and query.startswith(walk["address"]) else "locality",
                "countryCode": country_code,
                "provider": "OpenStreetMap Nominatim",
            }
            cache[walk["id"]] = value
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n")
            return value
    cache[walk["id"]] = None
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n")
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-geocode", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    urls = listing_urls(session)
    if args.limit:
        urls = urls[: args.limit]
    print(f"Found {len(urls)} walk listings")

    walks = []
    for index, url in enumerate(urls, 1):
        walk = parse_walk(session, url)
        walks.append(walk)
        print(f"[{index:03}/{len(urls):03}] scraped {walk['title']}")
        time.sleep(0.12)

    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    confirmed_locations = verified_locations()
    if not args.skip_geocode:
        for index, walk in enumerate(walks, 1):
            location = geocode(session, walk, cache, confirmed_locations)
            walk["location"] = location
            state = "ok" if location else "FAILED"
            print(f"[{index:03}/{len(walks):03}] geocode {state}: {walk['title']}")
    else:
        for walk in walks:
            walk["location"] = confirmed_locations.get(
                walk["id"], MANUAL_LOCATIONS.get(walk["id"], cache.get(walk["id"]))
            )

    countries = Counter(walk["country"] for walk in walks)
    payload = {
        "meta": {
            "sourceUrl": SOURCE_URL,
            "eventDate": "2026-09-27",
            "scrapedAt": datetime.now(timezone.utc).isoformat(),
            "walkCount": len(walks),
            "mappedCount": sum(bool(walk.get("location")) for walk in walks),
            "countryCount": len(countries),
        },
        "countries": [
            {"country": country, "count": count}
            for country, count in sorted(countries.items(), key=lambda item: (-item[1], item[0]))
        ],
        "walks": walks,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {OUTPUT}: {len(walks)} walks, {payload['meta']['mappedCount']} mapped, {len(countries)} countries")


if __name__ == "__main__":
    main()
