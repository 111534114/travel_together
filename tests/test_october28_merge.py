import unittest
from unittest.mock import MagicMock

from app import app
from blueprints.member import _mentioned_user_ids, _notify_mentions, render_mentions


class October28MergeTests(unittest.TestCase):
    def setUp(self):
        self.members = [
            {"user_id": 1, "nickname": "小明", "full_name": "王小明"},
            {"user_id": 2, "nickname": "小美", "full_name": "陳小美"},
            {"user_id": 3, "nickname": "阿華", "full_name": "林阿華"},
        ]

    def test_mentions_match_members_and_all_without_partial_all(self):
        self.assertEqual(_mentioned_user_ids("請 @小美 看看", self.members), {2})
        self.assertEqual(_mentioned_user_ids("@ALL 一起討論", self.members), {1, 2, 3})
        self.assertEqual(_mentioned_user_ids("@所有人 一起討論", self.members), {1, 2, 3})
        self.assertEqual(_mentioned_user_ids("@allen 不應算全部", self.members), set())

    def test_mention_highlight_escapes_user_content(self):
        html = str(render_mentions("<script>@小美</script>", self.members))
        self.assertIn("&lt;script&gt;", html)
        self.assertIn('<span class="mention">@小美</span>', html)
        self.assertNotIn("<script>", html)

    def test_notifications_exclude_author_and_previously_mentioned_members(self):
        cursor = MagicMock()
        trip = {"trip_id": 9, "trip_name": "台北"}
        with app.test_request_context():
            _notify_mentions(cursor, trip, self.members, "@ALL 出發", "#chat", 1, exclude_ids={2})

        self.assertEqual(cursor.execute.call_count, 1)
        sql, values = cursor.execute.call_args.args
        self.assertIn("INSERT INTO notifications", sql)
        self.assertEqual(values[0], 3)
        self.assertEqual(values[5], "/member/trips/9#chat")
        self.assertEqual(values[-1], "mention")

    def test_updated_templates_compile(self):
        names = (
            "member/trip_detail.html",
            "member/announcements.html",
            "member/attractions.html",
            "member/attraction_rankings.html",
            "member/trip_form.html",
            "member/friend_groups/group_new.html",
            "content_admin/attractions/form.html",
            "content_admin/restaurants/form.html",
            "content_admin/accommodations/form.html",
            "visitor.html",
        )
        for name in names:
            with self.subTest(name=name):
                self.assertIsNotNone(app.jinja_env.get_template(name))


if __name__ == "__main__":
    unittest.main()
