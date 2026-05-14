# ParkFinder

ParkFinder is now a Playwright-first Ontario Parks recorder. It does **not** scrape hidden reservation endpoints with Python HTTP clients. Playwright-controlled Chromium is the only thing that accesses <https://reservations.ontarioparks.ca/>.

## What the app does

1. Launches Chromium in headed mode.
2. Navigates to <https://reservations.ontarioparks.ca/>.
3. Lets you manually complete a search first.
4. Captures JSON responses from the browser with `page.on("response")`.
5. Saves matching JSON responses to `captured-responses.json`.
6. Extracts `page.locator("body").inner_text()` and saves it to `results-text.txt`.
7. Saves a screenshot to `results.png`.
8. Avoids direct Python `requests`, `httpx`, `aiohttp`, or `urllib` calls to Ontario Parks reservation APIs.

## Install and run the recorder

```bash
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
python3 -m parkfinder.playwright_recorder
```

When Chromium opens, use the Ontario Parks site normally and complete the search you care about. Then return to the terminal and press Enter. The recorder writes:

- `captured-responses.json` — JSON network responses whose URLs mention availability, inventory, campground, facility, search, reservation, or map data.
- `results-text.txt` — visible page text after your search.
- `results.png` — a screenshot of the results page.
- `browser-state.json` — browser cookies/local storage for later runs.

## Optional local UI

```bash
python3 -m parkfinder.server
```

Open <http://127.0.0.1:8000>. The UI is instructional and has a health check only; it does not scrape Ontario Parks itself.

## Codegen for the next step

Use Playwright codegen to discover selectors for automating the exact browser flow after the manual recorder works:

```bash
python3 -m playwright codegen https://reservations.ontarioparks.ca/
```

Paste the generated selectors and a representative sample from `captured-responses.json` into the next development pass. That is when the app can safely automate the visible browser flow and parse the actual JSON shape.
