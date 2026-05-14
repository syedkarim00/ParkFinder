from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ontario import OntarioParksClient, result_dicts, search_all_parks, summer_weekends


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan every Ontario Parks reservable campground for summer Friday-Sunday availability.")
    parser.add_argument("--year", type=int, required=True, help="Summer season year to scan, e.g. 2026")
    parser.add_argument("--output", type=Path, default=Path("results/ontario-parks-summer.json"))
    parser.add_argument("--include-all-sites", action="store_true", help="Include non-water-adjacent results too")
    parser.add_argument("--party-size", type=int, default=4)
    parser.add_argument("--equipment-id", default="-32768")
    parser.add_argument("--sub-equipment-id", default="-32766")
    parser.add_argument("--max-results", type=int, default=50000)
    parser.add_argument("--pause-seconds", type=float, default=0.12)
    args = parser.parse_args()

    weekends = summer_weekends(args.year)
    client = OntarioParksClient(pause_seconds=args.pause_seconds)
    results = search_all_parks(
        client,
        weekends,
        party_size=args.party_size,
        equipment_id=args.equipment_id,
        sub_equipment_id=args.sub_equipment_id,
        water_first=not args.include_all_sites,
        max_results=args.max_results,
    )
    payload = {
        "year": args.year,
        "weekends": [weekend.__dict__ for weekend in weekends],
        "resultCount": len(results),
        "results": result_dicts(results),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {len(results)} results to {args.output}")


if __name__ == "__main__":
    main()
