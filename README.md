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

This project is independent and is not an official Great Global Greyhound Walk website. Visitors should confirm event details on the linked official listing before travelling.
