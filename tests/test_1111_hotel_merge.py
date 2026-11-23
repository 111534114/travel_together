import unittest

import airports
import flight_links
from app import _parse_guest_party
from serpapi_hotels import _guest_params


class November11HotelMergeTests(unittest.TestCase):
    def test_guest_party_adds_rooms_and_maps_infant_age_for_serpapi(self):
        party = _parse_guest_party({
            "guests": "5", "rooms": "1", "children": "1", "child_ages": "0",
        })
        self.assertEqual(party["rooms"], 2)
        self.assertEqual(party["adults_per_room"], 3)
        self.assertEqual(party["ages_per_room"], [1])
        self.assertEqual(_guest_params(party["adults_per_room"], party["ages_per_room"]), {
            "adults": 3, "children": 1, "children_ages": "1",
        })

    def test_country_search_keeps_full_city_airport_catalog(self):
        # 機場清單收所有有定期航班的機場(含國內小機場，如 GKA)；名稱是「飛行場」的(如札幌飛行場 OKD)不收。
        self.assertIsNotNone(airports.get_airport("KEF"))
        self.assertIsNotNone(airports.get_airport("GKA"))
        self.assertIsNone(airports.get_airport("OKD"))
        self.assertTrue({"KEF", "RKV"} <= {airport["iata"] for airport in airports.get_country_airports("Iceland")})


if __name__ == "__main__":
    unittest.main()
