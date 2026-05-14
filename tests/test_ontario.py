import unittest
from datetime import date

from parkfinder.ontario import friday_to_sunday_weekends, summarize_captured_text, water_score
from parkfinder.playwright_recorder import date_button_name, is_interesting_url, resource_icon_selector, summarize_visible_text
from parkfinder.server import explain_error


class ParkFinderHelpersTest(unittest.TestCase):
    def test_friday_to_sunday_weekends(self):
        weekends = friday_to_sunday_weekends(date(2026, 6, 1), date(2026, 6, 15))
        self.assertEqual([w.start for w in weekends], ["2026-06-05", "2026-06-12"])
        self.assertEqual([w.end for w in weekends], ["2026-06-07", "2026-06-14"])

    def test_water_score_prefers_shoreline_metadata(self):
        score, reasons = water_score("42", {"Site Type": ["Lakefront"], "Distance to Beach": "35 m"})
        self.assertGreaterEqual(score, 30)
        self.assertIn("lakefront", reasons)
        self.assertIn("Distance to Beach: 35m", reasons)

    def test_summarize_captured_text(self):
        summary = summarize_captured_text("results-text.txt", "Waterfront campsite 42 is available")
        self.assertTrue(summary.has_available_word)
        self.assertGreater(summary.water_score, 0)

    def test_explain_error_describes_connection_refused(self):
        message = explain_error(Exception("[Errno 111] Connection refused"))
        self.assertIn("python3 -m parkfinder.server", message)

    def test_playwright_recorder_filters_interesting_urls(self):
        self.assertTrue(is_interesting_url("https://example.test/api/availability/search"))
        self.assertFalse(is_interesting_url("https://example.test/static/app.js"))


    def test_codegen_helpers_match_recorded_selectors(self):
        self.assertEqual(date_button_name("2026-06-05"), "June 5,")
        self.assertEqual(resource_icon_selector("-2147474195"), '[id="resourceSvg[-2147474195]"] > .icon-shape')

    def test_playwright_recorder_summarizes_visible_text(self):
        summary = summarize_visible_text("Site 42 is available for this campsite search")
        self.assertTrue(summary["has_available_word"])
        self.assertFalse(summary["has_no_availability_word"])


if __name__ == "__main__":
    unittest.main()
