from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from .ontario import summarize_captured_text

START_URL = "https://reservations.ontarioparks.ca/"
DEFAULT_KEYWORDS = (
    "availability",
    "inventory",
    "campground",
    "facility",
    "search",
    "reservation",
    "mapdata",
)


@dataclass(frozen=True)
class CodegenSearchConfig:
    park_name: str = "Algonquin - Kiosk"
    arrival: str = "2026-06-05"
    departure: str = "2026-06-07"
    equipment_name: str = "Single Tent"
    resource_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RecorderConfig:
    start_url: str = START_URL
    output_path: Path = Path("captured-responses.json")
    body_text_path: Path = Path("results-text.txt")
    screenshot_path: Path = Path("results.png")
    state_path: Path = Path("browser-state.json")
    headless: bool = False
    slow_mo_ms: int = 150
    timeout_ms: int = 60000
    manual: bool = True
    keywords: tuple[str, ...] = DEFAULT_KEYWORDS
    codegen_search: CodegenSearchConfig | None = None


def is_interesting_url(url: str, keywords: Iterable[str] = DEFAULT_KEYWORDS) -> bool:
    lower_url = url.lower()
    return any(keyword.lower() in lower_url for keyword in keywords)


def date_button_name(value: str) -> str:
    parsed = date.fromisoformat(value)
    return f"{parsed.strftime('%B')} {parsed.day},"


def next_month_button_name(value: str) -> str:
    parsed = date.fromisoformat(value)
    return f"View next month, {parsed.strftime('%B')}"


def resource_icon_selector(resource_id: str) -> str:
    return f'[id="resourceSvg[{resource_id}]"] > .icon-shape'


def summarize_visible_text(body_text: str) -> dict[str, Any]:
    summary = summarize_captured_text("visible-page-text", body_text)
    return {
        "has_available_word": summary.has_available_word,
        "has_no_availability_word": summary.has_no_availability_word,
        "text_sample": summary.text_sample,
        "water_score": summary.water_score,
        "water_reasons": summary.water_reasons,
    }


def load_playwright():
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Run `python3 -m pip install -r requirements.txt` "
            "and then `python3 -m playwright install chromium`."
        ) from exc
    return sync_playwright, PlaywrightTimeoutError


def run_codegen_search(page, search: CodegenSearchConfig) -> None:
    """Replay the selector flow produced by Playwright codegen for Ontario Parks.

    This keeps Ontario Parks access inside Chromium. These selectors came from the user-recorded
    codegen flow and may need to be regenerated if the site changes.
    """
    page.locator(".mat-mdc-select-arrow > svg").first.click()
    page.get_by_role("option", name=search.park_name).click()
    page.get_by_label("Arrival").click()
    page.get_by_role("button", name=next_month_button_name(search.arrival)).click()
    page.get_by_role("button", name=date_button_name(search.arrival)).click()
    page.get_by_role("button", name=date_button_name(search.departure)).click()
    page.locator("#mat-select-value-0").click()
    page.get_by_role("option", name=search.equipment_name).click()
    page.get_by_label("Search for availability").click()
    page.wait_for_load_state("networkidle", timeout=30000)
    for resource_id in search.resource_ids:
        page.locator(resource_icon_selector(resource_id)).click(timeout=10000)


def run_recorder(config: RecorderConfig) -> dict[str, Any]:
    """Use Chromium as the only process that accesses Ontario Parks.

    The recorder opens the public Ontario Parks site in a headed browser, waits for you to complete a
    normal search, captures JSON responses the browser naturally received via page.on("response"),
    and writes the visible result text plus screenshot to disk. It does not call hidden API URLs from
    Python HTTP clients.
    """
    sync_playwright, PlaywrightTimeoutError = load_playwright()
    captured: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for path in (config.output_path, config.body_text_path, config.screenshot_path, config.state_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    def handle_response(response):
        if not is_interesting_url(response.url, config.keywords):
            return
        record: dict[str, Any] = {
            "url": response.url,
            "status": response.status,
            "contentType": response.headers.get("content-type", ""),
        }
        try:
            request = response.request
            record["method"] = request.method
            record["resourceType"] = request.resource_type
        except Exception:
            pass
        try:
            if "application/json" in record["contentType"].lower():
                record["json"] = response.json()
                captured.append(record)
        except Exception as exc:
            record["error"] = str(exc)
            errors.append(record)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=config.headless, slow_mo=config.slow_mo_ms)
        context_options: dict[str, Any] = {
            "viewport": {"width": 1400, "height": 900},
            "locale": "en-CA",
            "timezone_id": "America/Toronto",
        }
        if config.state_path.exists():
            context_options["storage_state"] = str(config.state_path)
        context = browser.new_context(**context_options)
        page = context.new_page()
        page.on("response", handle_response)

        try:
            response = page.goto(config.start_url, wait_until="domcontentloaded", timeout=config.timeout_ms)
            print("Page status:", response.status if response else "No response")
            print("Page title:", page.title())
            if config.codegen_search:
                run_codegen_search(page, config.codegen_search)
            elif config.manual:
                input("Complete an Ontario Parks search in Chromium, then press Enter here to save results...")
            else:
                page.wait_for_load_state("networkidle", timeout=config.timeout_ms)

            page.screenshot(path=str(config.screenshot_path), full_page=True)
            body_text = page.locator("body").inner_text(timeout=10000)
            config.body_text_path.write_text(body_text, encoding="utf-8")
            context.storage_state(path=str(config.state_path))
        except PlaywrightTimeoutError as exc:
            errors.append({"error": f"Timed out: {exc}"})
            page.screenshot(path=str(config.screenshot_path), full_page=True)
        finally:
            context.close()
            browser.close()

    payload = {
        "startUrl": config.start_url,
        "keywords": list(config.keywords),
        "responseCount": len(captured),
        "responses": captured,
        "errors": errors,
    }
    config.output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def parse_args() -> RecorderConfig:
    parser = argparse.ArgumentParser(
        description="Open Ontario Parks in headed Chromium and capture natural JSON responses plus visible results."
    )
    parser.add_argument("--start-url", default=START_URL)
    parser.add_argument("--output", type=Path, default=Path("captured-responses.json"))
    parser.add_argument("--body-text", type=Path, default=Path("results-text.txt"))
    parser.add_argument("--screenshot", type=Path, default=Path("results.png"))
    parser.add_argument("--state", type=Path, default=Path("browser-state.json"))
    parser.add_argument("--headless", action="store_true", help="Run without a visible browser window; manual mode is disabled.")
    parser.add_argument("--slow-mo", type=int, default=150)
    parser.add_argument("--timeout", type=int, default=60000)
    parser.add_argument("--keyword", action="append", dest="keywords", help="URL keyword to capture; repeat for multiple keywords.")
    parser.add_argument("--use-codegen-flow", action="store_true", help="Run the recorded Algonquin/Kiosk search flow instead of waiting for manual input.")
    parser.add_argument("--park", default="Algonquin - Kiosk", help="Park option name for --use-codegen-flow.")
    parser.add_argument("--arrival", default="2026-06-05", help="Arrival date for --use-codegen-flow, YYYY-MM-DD.")
    parser.add_argument("--departure", default="2026-06-07", help="Departure date for --use-codegen-flow, YYYY-MM-DD.")
    parser.add_argument("--equipment", default="Single Tent", help="Equipment option name for --use-codegen-flow.")
    parser.add_argument("--click-resource", action="append", default=[], help="Optional resource ID to click after searching; repeat for multiple IDs.")
    args = parser.parse_args()
    codegen_search = None
    if args.use_codegen_flow:
        codegen_search = CodegenSearchConfig(
            park_name=args.park,
            arrival=args.arrival,
            departure=args.departure,
            equipment_name=args.equipment,
            resource_ids=tuple(args.click_resource),
        )
    return RecorderConfig(
        start_url=args.start_url,
        output_path=args.output,
        body_text_path=args.body_text,
        screenshot_path=args.screenshot,
        state_path=args.state,
        headless=args.headless,
        slow_mo_ms=args.slow_mo,
        timeout_ms=args.timeout,
        manual=not args.headless and codegen_search is None,
        keywords=tuple(args.keywords) if args.keywords else DEFAULT_KEYWORDS,
        codegen_search=codegen_search,
    )


def main() -> None:
    config = parse_args()
    payload = run_recorder(config)
    print(f"Captured {payload['responseCount']} JSON response(s) to {config.output_path}")
    print(f"Saved visible page text to {config.body_text_path}")
    print(f"Saved screenshot to {config.screenshot_path}")
    print(f"Saved browser state to {config.state_path}")


if __name__ == "__main__":
    main()
