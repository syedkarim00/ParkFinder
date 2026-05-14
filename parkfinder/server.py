from __future__ import annotations

import json
from datetime import date
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

from .ontario import (
    OntarioParksClient,
    friday_to_sunday_weekends,
    parse_location_inputs,
    result_dicts,
    search_all_parks,
    search_weekends,
)

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
DATA = ROOT / "data"

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/presets":
            self.send_json(load_presets())
            return
        if parsed.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/search":
            self.send_error(404)
            return
        try:
            payload = self.read_json()
            scan_mode = payload.get("scanMode", "all")
            locations_text = payload.get("locations", "")
            preset_ids = set(payload.get("presetIds", []))
            preset_locations = [p for p in load_presets() if p["id"] in preset_ids]
            combined = locations_text + "\n" + "\n".join(
                f"{p['name']}|{p['resourceLocationId']}|{p.get('mapId','')}" for p in preset_locations
            )
            locations = parse_location_inputs(combined)
            start = date.fromisoformat(payload["startDate"])
            end = date.fromisoformat(payload["endDate"])
            weekends = friday_to_sunday_weekends(start, end)
            if not weekends:
                raise ValueError("The date range does not contain any complete Friday-to-Sunday weekends.")
            client = OntarioParksClient(
                timeout=int(payload.get("timeout", 30)),
                pause_seconds=float(payload.get("pauseSeconds", 0.12)),
            )
            common = {
                "party_size": int(payload.get("partySize", 4)),
                "equipment_id": str(payload.get("equipmentId", "-32768")),
                "sub_equipment_id": str(payload.get("subEquipmentId", "-32766")),
                "water_first": bool(payload.get("waterFirst", True)),
                "max_results": int(payload.get("maxResults", 5000)),
            }
            if scan_mode == "selected":
                if not locations:
                    raise ValueError("Add at least one Ontario Parks result URL, resourceLocationId, or preset park for a selected-parks scan.")
                results = search_weekends(client, locations, weekends, **common)
            else:
                results = search_all_parks(client, weekends, **common)
            self.send_json({
                "mode": scan_mode,
                "weekends": [w.__dict__ for w in weekends],
                "results": result_dicts(results),
            })
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=400)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length).decode("utf-8") or "{}")

    def send_json(self, payload, status=200):
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

def load_presets():
    path = DATA / "parks.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())

def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    print("ParkFinder running at http://127.0.0.1:8000")
    print("Press Ctrl+C to stop.")
    server.serve_forever()

if __name__ == "__main__":
    main()
