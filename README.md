# ParkFinder

ParkFinder is a local web application for scraping the Ontario Parks reservation system for available **Friday-to-Sunday** campsite stays across June, July, August, and September. It can scan the reservation system's root map tree so you do **not** need to search each park or each weekend manually.

The app ranks matching sites using campsite metadata that suggests adjacency to bodies of water, because waterfront or near-water sites are preferred.

## Run the web app

```bash
python3 -m parkfinder.server
```

Open <http://127.0.0.1:8000> and click **Scan June–September weekends**. By default it scans every reservable Ontario Parks campground for every complete Friday-to-Sunday weekend between June 1 and September 30 of the selected year.

## Why this is not pure GitHub Pages

A GitHub Pages-only site cannot reliably run the scraper because Pages is static hosting: it has no Python backend, and browser CORS rules can block cross-origin reads of the Ontario Parks reservation API. ParkFinder therefore runs the scraper locally in Python and serves an easy browser UI from `http://127.0.0.1:8000`.

You can still publish generated results to GitHub Pages after running the CLI below, but the live scraping step must run somewhere with backend code.

## Run a full summer scan from the command line

```bash
python3 -m parkfinder.scan --year 2026 --output results/ontario-parks-2026.json
```

Use `--include-all-sites` if you want every available campsite rather than only those with water-adjacent metadata signals.

## What it scans

- The app starts at the Ontario Parks reservation root map ID used by the public reservation UI.
- It recursively follows region, park, campground, and sub-map links returned by `/api/maps/mapdatabyid`.
- For each terminal campsite map and each Friday-to-Sunday weekend, it collects available campsite resources from `resourceAvailabilityMap`.
- Selected-park mode is still available for pasted official result URLs or preset parks.

## Water-adjacent ranking

The reservation API exposes campsite attributes. ParkFinder decodes those attributes and scores sites higher when the site name or attributes include water-related signals such as:

- `waterfront`, `lakefront`, `riverfront`, `shoreline`
- `lakeside`, `riverside`, `beach`, `bay`, `creek`, `stream`
- water/shore/beach distance fields, when present

This is heuristic rather than a guarantee. Always verify the official campsite map and details before booking.

## Notes and limitations

- Ontario Parks reservations must still be completed on the official website. ParkFinder only searches and ranks public availability data, then links you back to the official booking page.
- Some networks block automated access to the reservation host. If a search fails with a network error, run ParkFinder on your personal network and retry.
- The full all-parks scan can take several minutes because it checks many campground maps for every summer weekend. Keep the default request pause enabled to be respectful.
- Reservations are subject to Ontario Parks rules and booking windows; future weekends beyond the reservation window may not be bookable yet.
