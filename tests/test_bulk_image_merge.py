import importlib
import io
import unittest
from unittest.mock import MagicMock, patch

from app import app


CASES = (
    ("attractions", "attraction_id", "attractions"),
    ("restaurants", "restaurant_id", "restaurants"),
    ("accommodations", "accommodation_id", "accommodations"),
)


class BulkImageMergeTests(unittest.TestCase):
    def _upload(self, module_name, id_column, folder, old_path, fail_update=False):
        module = importlib.import_module(f"blueprints.{module_name}")
        cursor = MagicMock()
        cursor.fetchall.return_value = [{id_column: 7, "name": "Test Place", "image_path": old_path}]
        if fail_update:
            def execute(sql, *args):
                if sql.startswith("UPDATE "):
                    raise RuntimeError("database update failed")
            cursor.execute.side_effect = execute
        connection = MagicMock()
        connection.cursor.return_value = cursor
        new_path = f"uploads/{folder}/new.jpg"

        with app.test_request_context(
            f"/content-admin/{module_name}/bulk-upload-images",
            method="POST",
            data={"images": (io.BytesIO(b"\xff\xd8\xff"), "Test Place.jpg")},
        ), patch.object(module, "get_db_connection", return_value=connection), \
                patch.object(module, "save_uploaded_image", return_value=new_path), \
                patch.object(module, "delete_uploaded_image") as delete, \
                patch.object(module, "log_action"), \
                patch.object(module, "render_template", return_value="done"):
            if fail_update:
                with self.assertRaises(RuntimeError):
                    module.bulk_upload_images.__wrapped__()
            else:
                self.assertEqual(module.bulk_upload_images.__wrapped__(), "done")
        return connection, delete, new_path

    def test_tracked_static_images_are_preserved_after_successful_upload(self):
        for module_name, id_column, folder in CASES:
            with self.subTest(module=module_name):
                connection, delete, _ = self._upload(
                    module_name, id_column, folder, "images/Test Place.jpg"
                )
                connection.commit.assert_called_once()
                delete.assert_not_called()

    def test_failed_database_update_removes_new_file_but_keeps_old_file(self):
        for module_name, id_column, folder in CASES:
            with self.subTest(module=module_name):
                old_path = f"uploads/{folder}/old.jpg"
                connection, delete, new_path = self._upload(
                    module_name, id_column, folder, old_path, fail_update=True
                )
                connection.rollback.assert_called_once()
                connection.commit.assert_not_called()
                delete.assert_called_once_with(new_path)


if __name__ == "__main__":
    unittest.main()
