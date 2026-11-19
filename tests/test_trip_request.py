import unittest
from datetime import date

import trip_request

COUNTRIES = [{"country_id": 1, "name": "台灣"}, {"country_id": 2, "name": "日本"}, {"country_id": 3, "name": "韓國"}]
CITIES = [
    {"city_id": 10, "country_id": 1, "name": "台北市"}, {"city_id": 11, "country_id": 1, "name": "新北市"},
    {"city_id": 20, "country_id": 2, "name": "北海道"}, {"city_id": 21, "country_id": 2, "name": "東京都"},
    {"city_id": 22, "country_id": 2, "name": "京都府"}, {"city_id": 30, "country_id": 3, "name": "首爾特別市"},
]
TODAY = date(2026, 11, 19)


def infer(text):
    return trip_request.complete(text, COUNTRIES, CITIES, today=TODAY)


class TripRequestTests(unittest.TestCase):
    def test_country_only_uses_main_city_and_default_dates(self):
        result = infer("我想要去日本")
        self.assertEqual((result["country_id"], result["city_id"]), (2, 21))
        self.assertEqual(result["start_date"], date(2026, 12, 3))
        self.assertEqual((result["end_date"] - result["start_date"]).days, 2)
        self.assertEqual(result["people_count"], 2)

    def test_full_sentence(self):
        result = infer("12 月想跟朋友去東京 5 天，預算每人 3 萬")
        self.assertEqual(result["city_id"], 21)
        self.assertEqual(result["start_date"], date(2026, 12, 1))
        self.assertEqual(result["end_date"], date(2026, 12, 5))
        self.assertEqual(result["budget"], 60000)

    def test_longest_name_wins_and_taiwanese_variant(self):
        self.assertEqual(infer("東京都內走走")["city_id"], 21)  # 不是「京都」
        self.assertEqual(infer("去臺北看夜市")["city_id"], 10)

    def test_explicit_date_nights_and_people(self):
        result = infer("12/24 去京都三天兩夜 3個人")
        self.assertEqual(result["city_id"], 22)
        self.assertEqual((result["start_date"], result["end_date"]), (date(2026, 12, 24), date(2026, 12, 26)))
        self.assertEqual(result["people_count"], 3)

    def test_past_date_moves_to_next_year_and_days_are_capped(self):
        result = infer("3/1 去首爾 10 天")
        self.assertEqual(result["start_date"], date(2027, 3, 1))
        self.assertEqual((result["end_date"] - result["start_date"]).days, trip_request.MAX_DAYS - 1)

    def test_unknown_destination_is_left_empty(self):
        self.assertNotIn("city_id", infer("想出去玩"))


if __name__ == "__main__":
    unittest.main()
