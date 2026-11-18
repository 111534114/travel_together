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
        # 城市搜尋保留完整機場清單；國家搜尋才依航線資料篩選主要機場。
        self.assertIsNotNone(airports.get_airport("KEF"))
        self.assertIsNotNone(airports.get_airport("GKA"))
        self.assertEqual(
            {airport["iata"] for airport in flight_links.country_airports("冰島")},
            {"KEF", "RKV"},
        )


if __name__ == "__main__":
    unittest.main()
