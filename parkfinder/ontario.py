from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from typing import Any, Iterable

BASE_URL = "https://reservations.ontarioparks.com"
API_BASE = f"{BASE_URL}/api"

WATER_POSITIVE = (
    "waterfront",
    "water front",
    "waterside",
    "water side",
    "water access",
    "water view",
    "waterview",
    "lakefront",
    "lake front",
    "lakeside",
    "lake side",
    "riverfront",
    "river front",
    "riverside",
    "river side",
    "shoreline",
    "shore line",
    "beach",
    "bay",
    "pond",
    "creek",
    "stream",
    "rapids",
    "canoe",
    "dock",
    "boat launch",
    "swimming",
)
WATER_NEGATIVE = (
    "not waterfront",
    "non-waterfront",
    "no water",
    "away from water",
    "comfort station",
    "dump station",
    "parking lot",
)

@dataclass(frozen=True)
class Weekend:
    start: str
    end: str
    nights: int = 2

@dataclass(frozen=True)
class LocationInput:
    name: str
    resource_location_id: str
    map_id: str | None = None
    raw_url: str | None = None

@dataclass
class SearchResult:
    park: str
    resource_location_id: str
    site_name: str
    resource_id: str
    weekend_start: str
    weekend_end: str
    availability_type: int | None
    water_score: int
    water_reasons: list[str]
    attributes: dict[str, Any]
    booking_url: str

class OntarioParksClient:
    def __init__(self, timeout: int = 30, pause_seconds: float = 0.12):
        self.timeout = timeout
        self.pause_seconds = pause_seconds
        self._attrs: dict[str, Any] | None = None
        self._cache: dict[str, Any] = {}

    def get_json(self, path_or_url: str, params: dict[str, Any] | None = None) -> Any:
        if path_or_url.startswith("http"):
            url = path_or_url
        else:
            url = f"{API_BASE}{path_or_url}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"
        if url in self._cache:
            return self._cache[url]
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "ParkFinder/1.0 (+local personal availability search)",
                "Accept": "application/json,text/plain,*/*",
                "Referer": "https://reservations.ontarioparks.ca/",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        self._cache[url] = data
        if self.pause_seconds:
            time.sleep(self.pause_seconds)
        return data

    def attributes(self) -> dict[str, Any]:
        if self._attrs is None:
            self._attrs = self.get_json("/attribute/filterable")
        return self._attrs

    def resources(self, resource_location_id: str) -> dict[str, Any]:
        return self.get_json("/resourcelocation/resources", {"resourceLocationId": resource_location_id})

    def availability(self, resource_id: str, start: str, end: str) -> dict[str, Any]:
        return self.get_json(
            "/availability/resourcestatus",
            {"resourceId": resource_id, "startDate": start, "endDate": end},
        )

def parse_location_inputs(text: str) -> list[LocationInput]:
    """Parse pasted result URLs, comma-separated IDs, or `Name|id|mapId` rows."""
    locations: list[LocationInput] = []
    for raw in re.split(r"[\n,]+", text or ""):
        item = raw.strip()
        if not item:
            continue
        if "|" in item and not item.startswith("http"):
            parts = [part.strip() for part in item.split("|")]
            if len(parts) >= 2:
                locations.append(LocationInput(parts[0] or parts[1], parts[1], parts[2] if len(parts) > 2 and parts[2] else None))
            continue
        if item.startswith("http"):
            parsed = urllib.parse.urlparse(item)
            params = urllib.parse.parse_qs(parsed.query)
            rid = first(params.get("resourceLocationId"))
            map_id = first(params.get("mapId"))
            if rid:
                locations.append(LocationInput(rid, rid, map_id, item))
            continue
        match = re.search(r"-?\d+", item)
        if match:
            rid = match.group(0)
            locations.append(LocationInput(rid, rid))
    dedup: dict[str, LocationInput] = {}
    for loc in locations:
        dedup[loc.resource_location_id] = loc
    return list(dedup.values())

def first(values: list[str] | None) -> str | None:
    return values[0] if values else None

def friday_to_sunday_weekends(start: date, end: date) -> list[Weekend]:
    weekends: list[Weekend] = []
    current = start
    while current.weekday() != 4:
        current += timedelta(days=1)
    while current + timedelta(days=2) <= end:
        weekends.append(Weekend(current.isoformat(), (current + timedelta(days=2)).isoformat()))
        current += timedelta(days=7)
    return weekends

def decode_site_attributes(site: dict[str, Any], attrs: dict[str, Any]) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    for defined in site.get("definedAttributes", []) or []:
        attr_id = str(defined.get("attributeDefinitionId"))
        meta = attrs.get(attr_id) or attrs.get(defined.get("attributeDefinitionId")) or {}
        name = localized_name(meta, "displayName") or attr_id
        if defined.get("value") not in (None, ""):
            value: Any = defined.get("value")
        else:
            values = []
            for value_id in defined.get("values", []) or []:
                meta_values = meta.get("values", {}) or {}
                value_meta = meta_values.get(str(value_id)) or meta_values.get(value_id) or {}
                values.append(localized_name(value_meta, "displayName") or str(value_id))
            value = values
        decoded[name] = value
    return decoded

def localized_name(obj: dict[str, Any], key: str = "name") -> str | None:
    values = obj.get("localizedValues") or []
    if values and isinstance(values[0], dict):
        return values[0].get(key) or values[0].get("name")
    return None

def site_name(site: dict[str, Any], fallback: str) -> str:
    return localized_name(site) or site.get("name") or fallback

def water_score(site_name_value: str, attributes: dict[str, Any]) -> tuple[int, list[str]]:
    haystack_parts = [site_name_value]
    for key, value in attributes.items():
        haystack_parts.append(str(key))
        if isinstance(value, list):
            haystack_parts.extend(str(v) for v in value)
        else:
            haystack_parts.append(str(value))
    haystack = " | ".join(haystack_parts).lower()
    score = 0
    reasons: list[str] = []
    for term in WATER_POSITIVE:
        if term in haystack:
            score += 12 if term in {"waterfront", "lakefront", "riverfront", "shoreline"} else 6
            reasons.append(term)
    for term in WATER_NEGATIVE:
        if term in haystack:
            score -= 18
            reasons.append(f"not {term}")
    # Numeric distance hints, if exposed by the reservation API.
    for key, value in attributes.items():
        key_l = key.lower()
        if "water" in key_l or "shore" in key_l or "beach" in key_l or "lake" in key_l:
            text = " ".join(str(v) for v in value) if isinstance(value, list) else str(value)
            number = re.search(r"\d+(?:\.\d+)?", text)
            if number:
                metres = float(number.group(0))
                if metres <= 50:
                    score += 20
                    reasons.append(f"{key}: {metres:g}m")
                elif metres <= 150:
                    score += 10
                    reasons.append(f"{key}: {metres:g}m")
    # Keep reasons concise and stable.
    seen = set()
    unique_reasons = []
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            unique_reasons.append(reason)
    return score, unique_reasons

def booking_url(location: LocationInput, weekend: Weekend, party_size: int, equipment_id: str, sub_equipment_id: str) -> str:
    params = {
        "resourceLocationId": location.resource_location_id,
        "searchTabGroupId": "0",
        "bookingCategoryId": "0",
        "startDate": weekend.start,
        "endDate": weekend.end,
        "nights": str(weekend.nights),
        "isReserving": "true",
        "equipmentId": equipment_id,
        "subEquipmentId": sub_equipment_id,
        "partySize": str(party_size),
        "searchTime": datetime.utcnow().isoformat(timespec="milliseconds"),
    }
    if location.map_id:
        params["mapId"] = location.map_id
    return f"{BASE_URL}/create-booking/results?{urllib.parse.urlencode(params)}"

def is_available(payload: dict[str, Any]) -> bool:
    return payload.get("availabilityType") == 0

def search_weekends(
    client: OntarioParksClient,
    locations: Iterable[LocationInput],
    weekends: Iterable[Weekend],
    party_size: int = 4,
    equipment_id: str = "-32768",
    sub_equipment_id: str = "-32766",
    water_first: bool = True,
    max_results: int = 200,
) -> list[SearchResult]:
    attrs = client.attributes()
    results: list[SearchResult] = []
    for location in locations:
        resources = client.resources(location.resource_location_id)
        for resource_id, site in resources.items():
            if not site:
                continue
            name = site_name(site, str(resource_id))
            decoded = decode_site_attributes(site, attrs)
            score, reasons = water_score(name, decoded)
            for weekend in weekends:
                availability = client.availability(str(resource_id), weekend.start, weekend.end)
                if not is_available(availability):
                    continue
                if water_first and score < 1:
                    continue
                results.append(
                    SearchResult(
                        park=location.name,
                        resource_location_id=location.resource_location_id,
                        site_name=name,
                        resource_id=str(resource_id),
                        weekend_start=weekend.start,
                        weekend_end=weekend.end,
                        availability_type=availability.get("availabilityType"),
                        water_score=score,
                        water_reasons=reasons,
                        attributes=decoded,
                        booking_url=booking_url(location, weekend, party_size, equipment_id, sub_equipment_id),
                    )
                )
                if len(results) >= max_results:
                    return sorted_results(results)
    return sorted_results(results)

def sorted_results(results: list[SearchResult]) -> list[SearchResult]:
    return sorted(results, key=lambda r: (-r.water_score, r.weekend_start, r.park, natural_key(r.site_name)))

def natural_key(value: str):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]

def result_dicts(results: list[SearchResult]) -> list[dict[str, Any]]:
    return [asdict(result) for result in results]
