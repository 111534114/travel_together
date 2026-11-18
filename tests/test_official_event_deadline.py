import unittest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from app import app
from blueprints.friend_groups import _event_registration_deadline, _event_registration_open
from blueprints.friend_groups_admin import _parse_registration_deadline


class OfficialEventDeadlineTests(unittest.TestCase):
    def test_cutoff_is_exclusive_and_defaults_to_event_start(self):
        event = {
            "event_date": date(2026, 12, 5), "start_time": timedelta(hours=9, minutes=30),
            "registration_deadline": None, "status": "open",
        }
        self.assertEqual(_event_registration_deadline(event), datetime(2026, 12, 5, 9, 30))
        self.assertTrue(_event_registration_open(event, datetime(2026, 12, 5, 9, 29)))
        self.assertFalse(_event_registration_open(event, datetime(2026, 12, 5, 9, 30)))
        event["registration_deadline"] = datetime(2026, 12, 4, 18)
        self.assertFalse(_event_registration_open(event, datetime(2026, 12, 4, 18)))

    def test_admin_deadline_must_precede_activity(self):
        form = {"event_date": "2026-12-05", "start_time": "09:30", "registration_deadline": "2026-12-04T18:00"}
        self.assertEqual(_parse_registration_deadline(form), (datetime(2026, 12, 4, 18), None))
        form["registration_deadline"] = "2026-12-05T09:30"
        self.assertIsNotNone(_parse_registration_deadline(form)[1])

    def test_expired_registration_cannot_insert_participant(self):
        client = app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 7
            session["role"] = "member"
        cursor = MagicMock()
        cursor.fetchone.return_value = {
            "event_id": 3, "status": "open", "event_date": date(2026, 12, 5),
            "start_time": timedelta(hours=9, minutes=30),
            "registration_deadline": datetime(2026, 12, 4, 18), "capacity": 10,
        }
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with patch("blueprints.friend_groups._connection_or_home", return_value=connection), \
             patch("blueprints.friend_groups._latest_application", return_value={"status": "approved"}), \
             patch("blueprints.friend_groups._event_registration_open", return_value=False):
            response = client.post("/member/friend-groups/events/3/register")
        self.assertEqual(response.status_code, 302)
        statements = "\n".join(str(call.args[0]) for call in cursor.execute.call_args_list)
        self.assertNotIn("INSERT INTO friend_group_event_participants", statements)
        connection.commit.assert_not_called()

    def test_templates_compile(self):
        for name in (
            "content_admin/friend_groups/event_form.html",
            "content_admin/friend_groups/events_list.html",
            "member/friend_groups/index.html",
            "member/friend_groups/event_detail.html",
        ):
            with self.subTest(name=name):
                self.assertIsNotNone(app.jinja_env.get_template(name))


if __name__ == "__main__":
    unittest.main()
