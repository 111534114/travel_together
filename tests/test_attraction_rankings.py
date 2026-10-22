import unittest
from unittest.mock import Mock, patch

from app import app
from attraction_rankings import count_attraction_rankings, fetch_attraction_rankings
from mysql.connector.errors import ProgrammingError
from utils import friend_group_feature_enabled


class RankingCursor:
    def __init__(self, rows=None, total=0):
        self.rows = rows or []
        self.total = total
        self.statements = []

    def execute(self, sql, params=()):
        self.statements.append((sql, params))

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return {"total": self.total}

    def close(self):
        pass


class AttractionRankingTests(unittest.TestCase):
    def test_admin_statistics_keeps_top_attractions_without_city_report(self):
        cursor = Mock()
        cursor.fetchone.side_effect = [
            dict(members=0, active_members=0, trips=0, public_trips=0, announcements=0),
            dict(active=0, favorites=0, itineraries=0),
        ]
        cursor.fetchall.side_effect = [[], [], []]
        connection = Mock()
        connection.cursor.return_value = cursor
        client = app.test_client()
        with client.session_transaction() as session:
            session.update(user_id=1, role="system_admin")
        with patch("app.get_db_connection", return_value=connection), \
             patch("app.fetch_attraction_rankings", return_value=[]):
            response = client.get("/system-admin/statistics")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("收藏景點前五名", html)
        self.assertIn("景點排行篩選", html)
        self.assertNotIn("熱門旅遊目的地前五名", html)
        self.assertNotIn('id="destinationBars"', html)
        self.assertEqual(html.count('data-metric="itineraries"'), 1)
        self.assertEqual(html.count('data-metric="favorites"'), 1)
        self.assertIn("臺灣縣市", html)
        self.assertIn('data-metric="itineraries"', html)
        self.assertIn('data-metric="favorites"', html)
        self.assertNotIn("縣市景點統計報表", html)
        self.assertEqual(cursor.execute.call_count, 5)

    def test_admin_favorite_ranking_filters_taiwan_county(self):
        cursor = RankingCursor(rows=[dict(name="九份老街", city="新北市", country="台灣",
                                         favorite_count=3, itinerary_count=1)])
        connection = Mock()
        connection.cursor.return_value = cursor
        client = app.test_client()
        with client.session_transaction() as session:
            session.update(user_id=1, role="system_admin")
        with patch("app.get_db_connection", return_value=connection):
            response = client.get("/system-admin/statistics/attractions?county=新北市")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["attractions"][0]["favorite_count"], 3)
        sql, params = cursor.statements[-1]
        self.assertIn("REPLACE(ci.name, '臺', '台') = %s", sql)
        self.assertIn("COALESCE(f.favorite_count, 0) > 0", sql)
        self.assertIn("ORDER BY favorite_count DESC, itinerary_count DESC", sql)
        self.assertEqual(params, ("新北市", 5, 0))

    def test_admin_favorite_ranking_rejects_invalid_county(self):
        client = app.test_client()
        with client.session_transaction() as session:
            session.update(user_id=1, role="system_admin")
        response = client.get("/system-admin/statistics/attractions?county=不存在")
        self.assertEqual(response.status_code, 400)

    def test_admin_itinerary_ranking_uses_selected_metric(self):
        cursor = RankingCursor(rows=[dict(name="台北101", city="台北市", country="台灣",
                                         favorite_count=0, itinerary_count=4)])
        connection = Mock()
        connection.cursor.return_value = cursor
        client = app.test_client()
        with client.session_transaction() as session:
            session.update(user_id=1, role="system_admin")
        with patch("app.get_db_connection", return_value=connection):
            response = client.get("/system-admin/statistics/attractions?metric=itineraries&country_id=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["attractions"][0]["itinerary_count"], 4)
        sql, params = cursor.statements[-1]
        self.assertIn("COALESCE(i.itinerary_count, 0) > 0", sql)
        self.assertIn("ORDER BY itinerary_count DESC, favorite_count DESC", sql)
        self.assertEqual(params, ("1", 5, 0))

    def test_admin_ranking_rejects_invalid_metric(self):
        client = app.test_client()
        with client.session_transaction() as session:
            session.update(user_id=1, role="system_admin")
        response = client.get("/system-admin/statistics/attractions?metric=views")
        self.assertEqual(response.status_code, 400)

    def test_missing_optional_friend_group_table_does_not_break_member_pages(self):
        cursor = Mock()
        cursor.execute.side_effect = ProgrammingError("missing app_settings", errno=1146)
        connection = Mock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/member/attractions"), \
             patch("db.get_db_connection", return_value=connection):
            self.assertFalse(friend_group_feature_enabled())
            self.assertFalse(friend_group_feature_enabled())
        self.assertEqual(cursor.execute.call_count, 1)

    def test_rankings_reuse_admin_order_and_apply_filters(self):
        cursor = RankingCursor(total=3)
        count = count_attraction_rankings(
            cursor, country_id="1", city_id="2", keyword="九份", positive_only=True,
        )
        rows = fetch_attraction_rankings(
            cursor, country_id="1", city_id="2", keyword="九份",
            positive_only=True, limit=20, offset=20,
        )
        self.assertEqual(count, 3)
        self.assertEqual(rows, [])
        sql, params = cursor.statements[-1]
        self.assertIn("a.status = 'active'", sql)
        self.assertIn("a.deleted_at IS NULL", sql)
        self.assertIn("t.deleted_at IS NULL", sql)
        self.assertIn("COALESCE(i.itinerary_count, 0) > 0", sql)
        self.assertIn("ORDER BY itinerary_count DESC, favorite_count DESC", sql)
        self.assertEqual(params, ("1", "2", "%九份%", "%九份%", 20, 20))

    def test_ranking_page_links_to_city_and_attraction_details(self):
        row = dict(attraction_id=9, country_id=1, city_id=2, name="九份老街",
                   address="新北市瑞芳區", image_path=None, country="台灣", city="新北市",
                   itinerary_count=4, favorite_count=2)
        cursor = RankingCursor(rows=[row], total=21)
        connection = Mock()
        connection.cursor.return_value = cursor
        client = app.test_client()
        with client.session_transaction() as session:
            session.update(user_id=1, role="member")
        with patch("blueprints.member.get_db_connection", return_value=connection), \
             patch("blueprints.member.get_countries", return_value=[]), \
             patch("blueprints.member.get_cities", return_value=[]), \
             patch.dict(app.jinja_env.globals, {"friend_group_feature_enabled": lambda: False}):
            response = client.get("/member/attractions/rankings?city_id=2&page=2")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("九份老街", html)
        self.assertIn("/member/attractions/9", html)
        self.assertIn("/member/attractions/rankings?country_id=1&amp;city_id=2", html)
        self.assertIn("加入行程 4 次", html)
        self.assertIn("第 2／2 頁", html)

    def test_explore_page_shows_ranking_preview_separate_from_curated_badge(self):
        attraction = dict(attraction_id=9, city_id=2, name="九份老街", address="新北市瑞芳區",
                          latitude=None, longitude=None, ticket_price=0, image_path=None,
                          is_popular=1, category_name="景點", country="台灣", city="新北市",
                          is_favorited=0)
        ranking = dict(attraction_id=9, name="九份老街", country="台灣", city="新北市",
                       itinerary_count=4)
        cursor = Mock()
        cursor.fetchall.side_effect = [[attraction], [ranking]]
        connection = Mock()
        connection.cursor.return_value = cursor
        client = app.test_client()
        with client.session_transaction() as session:
            session.update(user_id=1, role="member")
        with patch("blueprints.member.get_db_connection", return_value=connection), \
             patch("blueprints.member.get_countries", return_value=[]), \
             patch("blueprints.member.get_cities", return_value=[]), \
             patch("blueprints.member._addable_trips", return_value=[]), \
             patch.dict(app.jinja_env.globals, {"friend_group_feature_enabled": lambda: False}):
            response = client.get("/member/attractions?keyword=九份")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("景點排行榜", html)
        self.assertIn("加入行程 4 次", html)
        self.assertIn("精選", html)
        self.assertIn('data-ranking-open aria-haspopup="dialog"', html)
        self.assertIn('id="attractionRankingDialog"', html)
        self.assertIn('data-ranking-endpoint="/member/attractions/rankings/data"', html)
        self.assertIn('id="rankingChartTitle" data-ranking-title>加入行程景點前五名', html)
        self.assertIn('data-ranking-chart-list', html)
        self.assertIn('data-ranking-country=""', html)
        self.assertIn('data-ranking-metric="favorites"', html)
        self.assertIn('data-ranking-metric="itineraries"', html)
        self.assertNotIn('data-ranking-list', html)
        self.assertNotIn('href="/member/attractions/rankings?', html)

    def test_dialog_ranking_data_paginates_without_page_navigation(self):
        row = dict(attraction_id=9, name="九份老街", country="台灣", city="新北市",
                   itinerary_count=4, favorite_count=2)
        cursor = RankingCursor(rows=[row], total=12)
        connection = Mock()
        connection.cursor.return_value = cursor
        client = app.test_client()
        with client.session_transaction() as session:
            session.update(user_id=1, role="member")
        with patch("blueprints.member.get_db_connection", return_value=connection):
            response = client.get("/member/attractions/rankings/data?city_id=2&page=2")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["page"], 2)
        self.assertEqual(data["page_count"], 2)
        self.assertEqual(data["rankings"][0]["rank"], 11)
        self.assertEqual(data["rankings"][0]["detail_url"], "/member/attractions/9")
        self.assertEqual(cursor.statements[-1][1], ("2", 10, 10))
        self.assertNotIn("COALESCE(i.itinerary_count, 0) > 0", cursor.statements[-1][0])

    def test_dialog_top_ranking_filters_county_and_favorites(self):
        row = dict(attraction_id=9, name="九份老街", country="台灣", city="新北市",
                   itinerary_count=1, favorite_count=4)
        cursor = RankingCursor(rows=[row])
        connection = Mock()
        connection.cursor.return_value = cursor
        client = app.test_client()
        with client.session_transaction() as session:
            session.update(user_id=1, role="member")
        with patch("blueprints.member.get_db_connection", return_value=connection):
            response = client.get("/member/attractions/rankings/data?view=top&metric=favorites&county=新北市")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["rankings"][0]["detail_url"], "/member/attractions/9")
        self.assertEqual(response.get_json()["rankings"][0]["favorite_count"], 4)
        sql, params = cursor.statements[-1]
        self.assertIn("REPLACE(ci.name, '臺', '台') = %s", sql)
        self.assertIn("COALESCE(f.favorite_count, 0) > 0", sql)
        self.assertIn("ORDER BY favorite_count DESC, itinerary_count DESC", sql)
        self.assertEqual(params, ("新北市", 5, 0))

    def test_dialog_top_ranking_rejects_invalid_filter(self):
        client = app.test_client()
        with client.session_transaction() as session:
            session.update(user_id=1, role="member")
        response = client.get("/member/attractions/rankings/data?view=top&county=不存在")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
