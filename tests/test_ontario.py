import unittest
from datetime import date

from parkfinder.ontario import friday_to_sunday_weekends, parse_location_inputs, water_score


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


if __name__ == "__main__":
    unittest.main()
