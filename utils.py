import os
import uuid

from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def _extension(filename):
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


def save_uploaded_image(file_storage, subfolder):
    if file_storage is None or file_storage.filename == "":
        return None

    extension = _extension(file_storage.filename)

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("不支援的圖片格式，請上傳 png、jpg、jpeg、gif 或 webp")

    stored_name = f"{uuid.uuid4().hex}.{extension}"
    safe_name = secure_filename(stored_name)

    upload_dir = os.path.join(current_app.static_folder, "uploads", subfolder)
    os.makedirs(upload_dir, exist_ok=True)

    file_storage.save(os.path.join(upload_dir, safe_name))

    return f"uploads/{subfolder}/{safe_name}"


def delete_uploaded_image(relative_path):
    if not relative_path:
        return

    full_path = os.path.join(current_app.static_folder, relative_path)

    if os.path.isfile(full_path):
        try:
            os.remove(full_path)
        except OSError:
            pass


def get_countries(cursor):
    cursor.execute("SELECT country_id, name FROM countries ORDER BY name")
    return cursor.fetchall()


def get_cities(cursor, country_id=None):
    if country_id:
        cursor.execute(
            """
            SELECT city_id, country_id, name
            FROM cities
            WHERE country_id = %s
            ORDER BY name
            """,
            (country_id,)
        )
    else:
        cursor.execute(
            """
            SELECT city_id, country_id, name
            FROM cities
            ORDER BY name
            """
        )

    return cursor.fetchall()


def get_categories(cursor, category_type):
    cursor.execute(
        """
        SELECT category_id, category_name
        FROM categories
        WHERE category_type = %s
        ORDER BY category_name
        """,
        (category_type,)
    )
    return cursor.fetchall()
