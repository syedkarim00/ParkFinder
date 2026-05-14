import unittest
from datetime import date

from parkfinder.playwright_recorder import is_interesting_url, summarize_visible_text
from parkfinder.server import explain_error

from parkfinder.ontario import (
    Weekend,
    first_availability,
    friday_to_sunday_weekends,
    parse_location_inputs,
    resources_by_id,
    search_all_parks,
    water_score,
)


class OntarioHelpersTest(unittest.TestCase):
    def test_friday_to_sunday_weekends(self):
        weekends = friday_to_sunday_weekends(date(2026, 6, 1), date(2026, 6, 15))
        self.assertEqual([w.start for w in weekends], ["2026-06-05", "2026-06-12"])
        self.assertEqual([w.end for w in weekends], ["2026-06-07", "2026-06-14"])

    def test_parse_locations_from_url_and_pipe(self):
        locations = parse_location_inputs(
            "https://reservations.ontarioparks.com/create-booking/results?resourceLocationId=-2147483601&mapId=-2147483434\nBon Echo|-123|-456"
        )
        self.assertEqual(locations[0].resource_location_id, "-2147483601")
        self.assertEqual(locations[0].map_id, "-2147483434")
        self.assertEqual(locations[1].name, "Bon Echo")
        self.assertEqual(locations[1].resource_location_id, "-123")

    def test_water_score_prefers_shoreline_metadata(self):
        score, reasons = water_score("42", {"Site Type": ["Lakefront"], "Distance to Beach": "35 m"})
        self.assertGreaterEqual(score, 30)
        self.assertIn("lakefront", reasons)
        self.assertIn("Distance to Beach: 35m", reasons)

    def test_first_availability_keeps_zero_available_value(self):
        self.assertEqual(first_availability([{"availability": 0}]), 0)
        self.assertEqual(first_availability({"availabilityType": 7}), 7)

    def test_resources_by_id_accepts_resource_id(self):
        resources = resources_by_id({"resourcesOnMap": [{"resourceId": -1, "localizedValues": [{"name": "1"}]}]})
        self.assertIn("-1", resources)


    def test_explain_error_describes_ontario_parks_403(self):
        message = explain_error(Exception("HTTP Error 403: Forbidden"))
        self.assertIn("Ontario Parks returned HTTP 403 Forbidden", message)
        self.assertIn("cannot and should not bypass", message)
        self.assertIn("approved data access", message)


    def test_playwright_recorder_filters_interesting_urls(self):
        self.assertTrue(is_interesting_url("https://example.test/api/availability/search"))
        self.assertFalse(is_interesting_url("https://example.test/static/app.js"))

    def test_playwright_recorder_summarizes_visible_text(self):
        summary = summarize_visible_text("Site 42 is available for this campsite search")
        self.assertTrue(summary["has_available_word"])
        self.assertFalse(summary["has_no_availability_word"])

    def test_search_all_parks_walks_map_tree(self):
        class FakeClient:
            def attributes(self):
                return {"10": {"localizedValues": [{"displayName": "Site Type"}], "values": {"0": {"localizedValues": [{"displayName": "Waterfront"}]}}}}

            def map_data(self, map_id, start, end, party_size, equipment_id, sub_equipment_id):
                if map_id == "root":
                    return {"mapLinkLocalizedValues": {"child": [{"title": "Test Park"}]}}
                return {
                    "resourcesOnMap": [
                        {
                            "resourceId": "site-1",
                            "localizedValues": [{"name": "101"}],
                            "definedAttributes": [{"attributeDefinitionId": "10", "values": ["0"]}],
                        }
                    ],
                    "resourceAvailabilityMap": {"site-1": [{"availability": 0}]},
                }

        results = search_all_parks(FakeClient(), [Weekend("2026-06-05", "2026-06-07")], root_map_id="root")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].park, "Test Park")
        self.assertGreater(results[0].water_score, 0)


if __name__ == "__main__":
    unittest.main()
