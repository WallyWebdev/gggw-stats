# Great Global Greyhound Walk — Stats & Map

An independent Astro visualisation of the publicly listed 2026 Great Global Greyhound Walk schedule.

## Features

- Country and territory walk totals
- Interactive OpenStreetMap with every geocoded listing
- Walk detail popups linking to the official GGGW listing
- Searchable event directory
- Reproducible scraper for the current official schedule

## Local development

```bash
npm install
npm run dev
```

Refresh source data with:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
npm run scrape
npm run validate:live
npm run validate
```

## Confirmed precise locations

Human-confirmed coordinates are kept in `scripts/verified-locations.json`, keyed by the stable official walk ID. The scraper checks this file **before** its cache or OpenStreetMap geocoder, so a confirmed pin is never replaced or reprocessed when the directory is refreshed.

For a What3Words-derived coordinate, record the original code and its provenance with this shape:

```json
{
  "australia-queensland-dayboro": {
    "lat": -27.195918,
    "lng": 152.824540,
    "displayName": "Confirmed meeting point, Dayboro, Queensland",
    "query": "///fluke.chaos.tadpole",
    "precision": "exact meeting point",
    "sourceType": "what3words",
    "what3words": "///fluke.chaos.tadpole",
    "accuracy": "three-metre square",
    "coordinateStatus": "confirmed",
    "provider": "What3Words user-resolved coordinate"
  }
}
```

`npm run validate` rejects a W3W-derived coordinate unless it is marked confirmed, retains the matching original code, and records the three-metre-square accuracy.

This project is independent and is not an official Great Global Greyhound Walk website. Visitors should confirm event details on the linked official listing before travelling.
