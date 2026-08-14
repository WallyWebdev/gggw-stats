#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path
from urllib.parse import unquote
from urllib.request import Request, urlopen

SOURCE_URL = "https://greatglobalgreyhoundwalk.co.uk/walk-schedule/"
PATTERN = re.compile(r'https://greatglobalgreyhoundwalk\.co\.uk/walks/[^/"#?]+/')
EXPECTED_COUNTRY_CODES = {
    "Argentina": "ar", "Australia": "au", "Austria": "at", "Belgium": "be", "Bulgaria": "bg", "Canada": "ca",
    "Croatia": "hr", "Croatia (Hrvatska)": "hr", "Czech Republic": "cz", "England": "gb", "France": "fr", "Germany": "de", "Gibraltar": "gi",
    "Greece": "gr", "Guernsey": "gg", "Hungary": "hu", "Ireland": "ie", "Italy": "it", "Japan": "jp",
    "Jersey": "je", "Luxembourg": "lu", "Mexico": "mx", "Netherlands": "nl", "New Zealand": "nz", "Portugal": "pt", "San Marino": "sm",
    "Scotland": "gb", "Singapore": "sg", "South Africa": "za", "Sweden": "se", "Switzerland": "ch", "United Arab Emirates": "ae",
    "United States": "us", "Wales": "gb",
}

parser = argparse.ArgumentParser()
parser.add_argument("--live", action="store_true", help="Compare the dataset with the current official schedule")
args = parser.parse_args()

path = Path(__file__).resolve().parents[1] / "src" / "data" / "walks.json"
data = json.loads(path.read_text())
walks = data["walks"]
meta = data["meta"]

assert walks, "No walks were scraped"
assert len(walks) == meta["walkCount"]
assert len({walk["id"] for walk in walks}) == len(walks), "Duplicate walk IDs"
assert len({walk["sourceUrl"] for walk in walks}) == len(walks), "Duplicate source URLs"
assert sum(country["count"] for country in data["countries"]) == len(walks)
assert meta["mappedCount"] == len(walks), "Not every walk has been mapped"
assert all(PATTERN.fullmatch(walk["sourceUrl"]) for walk in walks), "Invalid official source URL"

for walk in walks:
    location = walk["location"]
    assert location, f"Missing location: {walk['title']}"
    assert -90 <= location["lat"] <= 90, f"Invalid latitude: {walk['title']}"
    assert -180 <= location["lng"] <= 180, f"Invalid longitude: {walk['title']}"
    assert location.get("query"), f"Missing geocode provenance: {walk['title']}"
    if location["precision"].startswith("published"):
        assert location.get("verificationUrl"), f"Missing manual verification source: {walk['title']}"
    elif location.get("sourceType") == "what3words":
        assert location.get("accuracy") == "three-metre square", f"Missing W3W accuracy record: {walk['title']}"
        assert location.get("what3words"), f"Missing W3W code record: {walk['title']}"
        assert location.get("coordinateStatus") == "confirmed", f"Unconfirmed W3W coordinate: {walk['title']}"
        normalise_w3w = lambda value: ".".join(re.findall(r"\w+", unquote(value))).casefold()
        assert normalise_w3w(location["what3words"]) in normalise_w3w(walk["what3words"]), (
            f"W3W code does not match listing: {walk['title']}"
        )
    elif location.get("sourceType") == "user-verified":
        assert location.get("coordinateStatus") == "confirmed", f"Unconfirmed user-verified coordinate: {walk['title']}"
    else:
        assert location.get("provider") == "OpenStreetMap Nominatim", f"Missing geocoder provider: {walk['title']}"
        assert location.get("countryCode") == EXPECTED_COUNTRY_CODES[walk["country"]], f"Wrong geocoder country: {walk['title']}"

if args.live:
    request = Request(SOURCE_URL, headers={"User-Agent": "GGGW-Stats-Validator/1.0"})
    html = urlopen(request, timeout=45).read().decode("utf-8", "replace")
    live_urls = set(PATTERN.findall(html))
    stored_urls = {walk["sourceUrl"] for walk in walks}
    assert live_urls == stored_urls, (
        f"Dataset differs from live schedule: missing={sorted(live_urls - stored_urls)}, "
        f"stale={sorted(stored_urls - live_urls)}"
    )

print(f"Validated {len(walks)} unique walks, {meta['mappedCount']} mapped, {meta['countryCount']} countries/territories" + (" against live schedule" if args.live else ""))
