# ParkFinder

ParkFinder is a local web application for scraping the Ontario Parks reservation system for available **Friday-to-Sunday** campsite stays across June, July, August, and September. It can scan the reservation system's root map tree so you do **not** need to search each park or each weekend manually.

The app ranks matching sites using campsite metadata that suggests adjacency to bodies of water, because waterfront or near-water sites are preferred.

## Run the web app

```bash
python3 -m parkfinder.server
```

Open <http://127.0.0.1:8000> and click **Scan June–September weekends**. By default it scans every reservable Ontario Parks campground for every complete Friday-to-Sunday weekend between June 1 and September 30 of the selected year.



## Why you might see `net::ERR_CONNECTION_REFUSED`

`net::ERR_CONNECTION_REFUSED` means your browser could not connect to the local ParkFinder server. This is different from an Ontario Parks HTTP 403. The usual causes are:

- The Python server is not running. Start it with `python3 -m parkfinder.server` and keep that terminal window open.
- You opened `static/index.html` directly from your filesystem. Instead, open <http://127.0.0.1:8000>.
- The server crashed or was stopped during a long scan. Check the terminal running `python3 -m parkfinder.server` for a traceback.
- Port 8000 is already in use by another app. Stop the other app, then restart ParkFinder.

You can verify the server is reachable with:

```bash
curl http://127.0.0.1:8000/api/health
```

## Recommended Playwright recorder workflow

The most reliable first step is the browser recorder, not the direct API scanner. It opens the real Ontario Parks site in Chromium, lets you complete a normal search, captures screenshots, saves visible page text, saves browser storage/cookies, and records JSON network responses that the browser naturally receives.

```bash
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
python3 -m parkfinder.playwright_recorder
```

When the browser opens, complete a search normally. Then return to the terminal and press Enter. The recorder writes:

- `captures/captured-responses.json` — JSON responses whose URLs mention availability, inventory, campground, facility, search, reservation, or map data.
- `captures/latest-page-text.txt` — visible page text after your search.
- `screenshots/debug-home.png` and `screenshots/debug-results.png` — screenshots for debugging selectors/results.
- `state/ontario-parks-browser-state.json` — browser cookies/local storage for later runs.

Use Playwright codegen to discover selectors for the next automation step:

```bash
python3 -m playwright codegen https://reservations.ontarioparks.ca/
```

Paste the generated selectors and a sample of `captured-responses.json` into the next development step, and the app can be extended to automate that exact browser flow and parse the real response structure.

## Why you might see HTTP 403

When you click **Scan**, your browser calls the local ParkFinder server at `http://127.0.0.1:8000`, and that Python server requests availability data from Ontario Parks. An HTTP 403 means Ontario Parks, or a network service in front of it, refused the automated request. Common causes include automated-traffic protection, request-volume limits, or reservation-site session checks.

ParkFinder cannot and should not bypass Ontario Parks traffic-protection controls. Legitimate next steps are to use the official reservation website, contact Ontario Parks to ask about approved data access, or make a much smaller, slower selected-parks scan if their terms allow automated personal use. Do not use IP rotation, proxy rotation, CAPTCHA workarounds, or other evasion techniques.

## Direct API scanner

The older direct scanner is still available, but it is more likely to hit HTTP 403 because it calls reservation endpoints from Python instead of letting the browser create the session naturally. Use it only after the Playwright recorder proves what data the site returns.

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
