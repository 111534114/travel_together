import unittest
from unittest.mock import MagicMock, patch

from flask import session

from app import app
from blueprints.friend_groups import apply


class GroupApplicationNoteTests(unittest.TestCase):
    def test_blank_note_is_rejected_before_writing(self):
        cursor = MagicMock()
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/member/friend-groups/apply", method="POST",
                                      data={"birthdate": "2000-01-01", "note": "   "}):
            session.update(user_id=7, role="member")
            with patch("blueprints.friend_groups._connection_or_home", return_value=connection), \
                 patch("blueprints.friend_groups._latest_application", return_value=None):
                response = apply()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(any("INSERT INTO friend_group_applications" in call.args[0]
                             for call in cursor.execute.call_args_list))
        connection.commit.assert_not_called()

    def test_note_is_saved_with_application(self):
        cursor = MagicMock()
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/member/friend-groups/apply", method="POST",
                                      data={"birthdate": "2000-01-01", "note": "想認識喜歡健行的旅伴"}):
            session.update(user_id=7, role="member")
            with patch("blueprints.friend_groups._connection_or_home", return_value=connection), \
                 patch("blueprints.friend_groups._latest_application", return_value=None):
                apply()
        self.assertTrue(any(call.args[1] == (7, "想認識喜歡健行的旅伴")
                            for call in cursor.execute.call_args_list
                            if "INSERT INTO friend_group_applications" in call.args[0]))
        connection.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
