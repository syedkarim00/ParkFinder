from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import date, timedelta
from typing import Any

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


@dataclass
class CapturedSearchSummary:
    source: str
    water_score: int
    water_reasons: list[str]
    has_available_word: bool
    has_no_availability_word: bool
    text_sample: str


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


def water_score(site_name_value: str, attributes: dict[str, Any] | None = None) -> tuple[int, list[str]]:
    attributes = attributes or {}
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
    return score, dedupe(reasons)


def summarize_captured_text(source: str, body_text: str) -> CapturedSearchSummary:
    lower_text = body_text.lower()
    unavailable_words = ("no availability", "no sites", "unavailable")
    available_words = ("available", "site", "campsite")
    score, reasons = water_score(body_text)
    return CapturedSearchSummary(
        source=source,
        water_score=score,
        water_reasons=reasons,
        has_available_word=any(word in lower_text for word in available_words),
        has_no_availability_word=any(word in lower_text for word in unavailable_words),
        text_sample=body_text[:3000],
    )


def dedupe(values: list[str]) -> list[str]:
    seen = set()
    unique = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def result_dicts(results: list[CapturedSearchSummary]) -> list[dict[str, Any]]:
    return [asdict(result) for result in results]
