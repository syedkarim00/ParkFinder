# ParkFinder

ParkFinder is a local web application for scanning the public Ontario Parks reservation API for available **Friday-to-Sunday** campsite stays across a summer date range. It ranks matching sites using campsite metadata that suggests adjacency to bodies of water, because waterfront or near-water sites are preferred.

## Why this is local

Ontario Parks reservations must still be completed on the official website. ParkFinder only helps you search and rank public availability data, then sends you to the official booking result URL.

## Run

```bash
python3 -m parkfinder.server
```

Open <http://127.0.0.1:8000>.

## How to search

1. Open <https://reservations.ontarioparks.ca/>.
2. Start a normal campsite search for a park/campground you care about.
3. Copy the official results URL from the browser address bar.
4. Paste one or more results URLs into ParkFinder.
5. Choose a summer date range, then scan.

ParkFinder automatically converts the date range into complete Friday-to-Sunday weekends and checks each campsite's availability for those two-night stays.

## Water-adjacent ranking

The reservation API exposes campsite attributes. ParkFinder decodes those attributes and scores sites higher when the site name or attributes include water-related signals such as:

- `waterfront`, `lakefront`, `riverfront`, `shoreline`
- `lakeside`, `riverside`, `beach`, `bay`, `creek`, `stream`
- water/shore/beach distance fields, when present

This is heuristic rather than a guarantee. Always verify the official campsite map and details before booking.

## Notes and limitations

- The app uses the publicly observed Ontario Parks endpoints `/api/attribute/filterable`, `/api/resourcelocation/resources`, and `/api/availability/resourcestatus`.
- Some networks block automated access to the reservation host. If a search fails with a network error, run ParkFinder on your personal network or paste fewer parks and retry.
- Preset park IDs in `data/parks.json` are convenience examples from publicly shared result URLs. Pasted official URLs are more reliable because Ontario Parks can change IDs or maps over time.
- Be respectful: search only the parks you need and keep the default request pause enabled.
