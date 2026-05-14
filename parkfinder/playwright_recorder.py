from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

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
class RecorderConfig:
    start_url: str = START_URL
    state_path: Path = Path("state/ontario-parks-browser-state.json")
    output_path: Path = Path("captures/captured-responses.json")
    body_text_path: Path = Path("captures/latest-page-text.txt")
    screenshot_dir: Path = Path("screenshots")
    headless: bool = False
    slow_mo_ms: int = 150
    timeout_ms: int = 60000
    manual: bool = True
    keywords: tuple[str, ...] = DEFAULT_KEYWORDS


def is_interesting_url(url: str, keywords: Iterable[str] = DEFAULT_KEYWORDS) -> bool:
    lower_url = url.lower()
    return any(keyword.lower() in lower_url for keyword in keywords)


def summarize_visible_text(body_text: str) -> dict[str, Any]:
    lower_text = body_text.lower()
    unavailable_words = ("no availability", "no sites", "unavailable")
    available_words = ("available", "site", "campsite")
    return {
        "has_available_word": any(word in lower_text for word in available_words),
        "has_no_availability_word": any(word in lower_text for word in unavailable_words),
        "text_sample": body_text[:3000],
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


def run_recorder(config: RecorderConfig) -> dict[str, Any]:
    """Open Ontario Parks in a real browser and capture natural page/network output.

    This intentionally does not call hidden reservation endpoints directly. You complete the search in
    the browser, and the recorder saves screenshots, visible page text, storage state, and JSON
    responses that the browser naturally received.
    """
    sync_playwright, PlaywrightTimeoutError = load_playwright()
    captured: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    config.body_text_path.parent.mkdir(parents=True, exist_ok=True)
    config.screenshot_dir.mkdir(parents=True, exist_ok=True)
    config.state_path.parent.mkdir(parents=True, exist_ok=True)

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
            page.screenshot(path=str(config.screenshot_dir / "debug-home.png"), full_page=True)
            print("Page status:", response.status if response else "No response")
            print("Page title:", page.title())
            if config.manual:
                input("Complete an Ontario Parks search in the browser, then press Enter here to capture results...")
            else:
                page.wait_for_load_state("networkidle", timeout=config.timeout_ms)

            page.screenshot(path=str(config.screenshot_dir / "debug-results.png"), full_page=True)
            body_text = page.locator("body").inner_text(timeout=10000)
            config.body_text_path.write_text(body_text, encoding="utf-8")
            context.storage_state(path=str(config.state_path))
        except PlaywrightTimeoutError as exc:
            page.screenshot(path=str(config.screenshot_dir / "timeout-debug.png"), full_page=True)
            errors.append({"error": f"Timed out: {exc}"})
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
        description="Open Ontario Parks in Playwright and capture visible page text plus natural JSON network responses."
    )
    parser.add_argument("--start-url", default=START_URL)
    parser.add_argument("--state", type=Path, default=Path("state/ontario-parks-browser-state.json"))
    parser.add_argument("--output", type=Path, default=Path("captures/captured-responses.json"))
    parser.add_argument("--body-text", type=Path, default=Path("captures/latest-page-text.txt"))
    parser.add_argument("--screenshots", type=Path, default=Path("screenshots"))
    parser.add_argument("--headless", action="store_true", help="Run without a visible browser window; manual mode is disabled.")
    parser.add_argument("--slow-mo", type=int, default=150)
    parser.add_argument("--timeout", type=int, default=60000)
    parser.add_argument("--keyword", action="append", dest="keywords", help="URL keyword to capture; repeat for multiple keywords.")
    args = parser.parse_args()
    return RecorderConfig(
        start_url=args.start_url,
        state_path=args.state,
        output_path=args.output,
        body_text_path=args.body_text,
        screenshot_dir=args.screenshots,
        headless=args.headless,
        slow_mo_ms=args.slow_mo,
        timeout_ms=args.timeout,
        manual=not args.headless,
        keywords=tuple(args.keywords) if args.keywords else DEFAULT_KEYWORDS,
    )


def main() -> None:
    config = parse_args()
    payload = run_recorder(config)
    print(f"Captured {payload['responseCount']} JSON response(s) to {config.output_path}")
    print(f"Saved visible page text to {config.body_text_path}")
    print(f"Saved browser state to {config.state_path}")


if __name__ == "__main__":
    main()
