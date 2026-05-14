from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import UTC, date, datetime, timedelta
from typing import Any, Iterable
from uuid import uuid4

BASE_URL = "https://reservations.ontarioparks.com"
API_BASE = f"{BASE_URL}/api"
ROOT_MAP_ID = "-2147483464"

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

@dataclass(frozen=True)
class MapNode:
    map_id: str
    name: str
    path: tuple[str, ...]

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
        return self.request_json("GET", path_or_url, params=params)

    def post_json(self, path_or_url: str, payload: dict[str, Any], params: dict[str, Any] | None = None) -> Any:
        return self.request_json("POST", path_or_url, params=params, payload=payload)

    def request_json(
        self,
        method: str,
        path_or_url: str,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        if path_or_url.startswith("http"):
            url = path_or_url
        else:
            url = f"{API_BASE}{path_or_url}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"
        body = None
        cache_key = f"{method} {url} {json.dumps(payload, sort_keys=True) if payload else ''}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        headers = {
            "User-Agent": "ParkFinder/2.0 (+local personal availability search)",
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://reservations.ontarioparks.ca/",
        }
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        self._cache[cache_key] = data
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

    def map_data(
        self,
        map_id: str,
        start: str,
        end: str,
        party_size: int = 4,
        equipment_id: str = "-32768",
        sub_equipment_id: str = "-32766",
        daily: bool = False,
    ) -> dict[str, Any]:
        payload = {
            "mapId": str(map_id),
            "cartUid": str(uuid4()),
            "bookingUid": str(uuid4()),
            "cartTransactionUid": str(uuid4()),
            "bookingCategoryId": 0,
            "startDate": as_reservation_datetime(start),
            "endDate": as_reservation_datetime(end),
            "isReserving": True,
            "getDailyAvailability": daily,
            "partySize": party_size,
            "filterData": "[]",
            "equipmentCategoryId": int(equipment_id),
            "subEquipmentCategoryId": int(sub_equipment_id),
            "boatLength": None,
            "boatDraft": None,
            "boatWidth": None,
            "generateBreadcrumbs": False,
            "resourceAccessPointId": None,
        }
        return self.post_json("/maps/mapdatabyid", payload, {"seed": datetime.now(UTC).isoformat(timespec="milliseconds")})

def as_reservation_datetime(value: str) -> str:
    if "T" in value:
        return value
    return f"{value}T00:00:00.000Z"

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

def summer_weekends(year: int) -> list[Weekend]:
    return friday_to_sunday_weekends(date(year, 6, 1), date(year, 9, 30))

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
                if isinstance(meta_values, list):
                    value_meta = meta_values[value_id] if isinstance(value_id, int) and value_id < len(meta_values) else {}
                else:
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
        "searchTime": datetime.now(UTC).isoformat(timespec="milliseconds"),
    }
    if location.map_id:
        params["mapId"] = location.map_id
    return f"{BASE_URL}/create-booking/results?{urllib.parse.urlencode(params)}"

def map_booking_url(map_id: str, weekend: Weekend, party_size: int, equipment_id: str, sub_equipment_id: str) -> str:
    params = {
        "mapId": map_id,
        "searchTabGroupId": "0",
        "bookingCategoryId": "0",
        "startDate": weekend.start,
        "endDate": weekend.end,
        "nights": str(weekend.nights),
        "isReserving": "true",
        "equipmentId": equipment_id,
        "subEquipmentId": sub_equipment_id,
        "partySize": str(party_size),
        "searchTime": datetime.now(UTC).isoformat(timespec="milliseconds"),
    }
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

def search_all_parks(
    client: OntarioParksClient,
    weekends: Iterable[Weekend],
    root_map_id: str = ROOT_MAP_ID,
    party_size: int = 4,
    equipment_id: str = "-32768",
    sub_equipment_id: str = "-32766",
    water_first: bool = True,
    max_results: int = 5000,
) -> list[SearchResult]:
    """Scan the Ontario Parks root map tree instead of requiring per-park URLs.

    The reservation system's root map links to regions, parks, campgrounds and site maps. For each
    requested weekend we recursively load that tree and collect available resources from terminal maps.
    """
    attrs = client.attributes()
    results: list[SearchResult] = []
    seen: set[tuple[str, str, str]] = set()
    for weekend in weekends:
        for node, data in iter_site_maps(client, root_map_id, weekend, party_size, equipment_id, sub_equipment_id):
            resources = resources_by_id(data)
            availability_map = data.get("resourceAvailabilityMap") or {}
            for resource_id, availability_entries in availability_map.items():
                availability = first_availability(availability_entries)
                if availability != 0:
                    continue
                site = resources.get(str(resource_id)) or resources.get(resource_id) or {}
                name = site_name(site, str(resource_id))
                decoded = decode_site_attributes(site, attrs) if site else {}
                score, reasons = water_score(name, decoded)
                if water_first and score < 1:
                    continue
                key = (str(resource_id), weekend.start, weekend.end)
                if key in seen:
                    continue
                seen.add(key)
                park_name = best_park_name(node.path)
                results.append(
                    SearchResult(
                        park=park_name,
                        resource_location_id=str(node.map_id),
                        site_name=name,
                        resource_id=str(resource_id),
                        weekend_start=weekend.start,
                        weekend_end=weekend.end,
                        availability_type=availability,
                        water_score=score,
                        water_reasons=reasons,
                        attributes={"Map path": list(node.path), **decoded},
                        booking_url=map_booking_url(node.map_id, weekend, party_size, equipment_id, sub_equipment_id),
                    )
                )
                if len(results) >= max_results:
                    return sorted_results(results)
    return sorted_results(results)

def iter_site_maps(
    client: OntarioParksClient,
    root_map_id: str,
    weekend: Weekend,
    party_size: int,
    equipment_id: str,
    sub_equipment_id: str,
):
    stack = [MapNode(str(root_map_id), "Ontario Parks", ("Ontario Parks",))]
    visited: set[str] = set()
    while stack:
        node = stack.pop()
        if node.map_id in visited:
            continue
        visited.add(node.map_id)
        data = client.map_data(node.map_id, weekend.start, weekend.end, party_size, equipment_id, sub_equipment_id)
        links = data.get("mapLinkLocalizedValues") or {}
        if links:
            for child_id, values in reversed(list(links.items())):
                child_name = localized_title(values) or str(child_id)
                stack.append(MapNode(str(child_id), child_name, (*node.path, child_name)))
            continue
        if data.get("resourceAvailabilityMap"):
            yield node, data

def localized_title(values: Any) -> str | None:
    if isinstance(values, list) and values and isinstance(values[0], dict):
        return values[0].get("title") or values[0].get("name")
    if isinstance(values, dict):
        return values.get("title") or values.get("name")
    return None

def resources_by_id(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    resources: dict[str, dict[str, Any]] = {}
    for resource in data.get("resourcesOnMap", []) or []:
        resource_id = extract_resource_id(resource)
        if resource_id is not None:
            resources[str(resource_id)] = resource
    return resources

def extract_resource_id(resource: dict[str, Any]) -> str | None:
    for key in ("resourceId", "id", "resourceID", "resource_id"):
        if key in resource and resource[key] is not None:
            return str(resource[key])
    return None

def first_availability(entries: Any) -> int | None:
    if isinstance(entries, list) and entries:
        first_entry = entries[0]
        if isinstance(first_entry, dict):
            if "availability" in first_entry:
                return first_entry["availability"]
            return first_entry.get("availabilityType")
    if isinstance(entries, dict):
        if "availability" in entries:
            return entries["availability"]
        return entries.get("availabilityType")
    return None

def best_park_name(path: tuple[str, ...]) -> str:
    useful = [part for part in path if part and part != "Ontario Parks"]
    if not useful:
        return "Ontario Parks"
    if len(useful) >= 2:
        return " · ".join(useful[-2:])
    return useful[0]

def sorted_results(results: list[SearchResult]) -> list[SearchResult]:
    return sorted(results, key=lambda r: (r.weekend_start, r.park, -r.water_score, natural_key(r.site_name)))

def natural_key(value: str):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]

def result_dicts(results: list[SearchResult]) -> list[dict[str, Any]]:
    return [asdict(result) for result in results]
