"""One-time local setup: create a least-privilege MySQL user and private .env keys.

Run this only on the desktop that already owns the travel_together database.
The generated passwords are never printed or committed to Git.
"""

import re
import secrets
from pathlib import Path

import mysql.connector
from dotenv import dotenv_values, set_key

from config import DB_CONFIG


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"


def main():
    if not ENV_PATH.is_file():
        raise SystemExit("找不到專案根目錄的 .env；尚未修改資料庫。")

    existing = dotenv_values(ENV_PATH)
    if existing.get("DB_USER") or existing.get("DB_PASSWORD"):
        raise SystemExit(".env 已有 DB_USER 或 DB_PASSWORD；為避免覆蓋現有設定，請先人工確認。")

    database = DB_CONFIG["database"]
    if not re.fullmatch(r"[A-Za-z0-9_]+", database):
        raise SystemExit("資料庫名稱含有不支援的字元；尚未修改資料庫。")

    username = "travel_web_" + secrets.token_hex(3)
    password = secrets.token_urlsafe(36)
    secret_key = existing.get("FLASK_SECRET_KEY") or secrets.token_urlsafe(48)

    admin = mysql.connector.connect(**DB_CONFIG)
    try:
        cursor = admin.cursor()
        try:
            cursor.execute(
                "SELECT 1 FROM information_schema.schemata WHERE schema_name=%s",
                (database,),
            )
            if cursor.fetchone() is None:
                raise SystemExit("找不到 travel_together 資料庫；尚未建立網站帳號。")

            # 帳號名稱由本程式產生，只有 ASCII 字母、數字與底線。
            cursor.execute(f"CREATE USER '{username}'@'localhost' IDENTIFIED BY %s", (password,))
            cursor.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON `{database}`.* "
                f"TO '{username}'@'localhost'"
            )
        finally:
            cursor.close()
    finally:
        admin.close()

    # 先驗證新帳號能讀取網站需要的資料，再把設定存入 .env。
    website_db = mysql.connector.connect(
        host="localhost", port=DB_CONFIG["port"], user=username,
        password=password, database=database, use_pure=True,
    )
    try:
        cursor = website_db.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM users")
            cursor.fetchone()
        finally:
            cursor.close()
    finally:
        website_db.close()

    for key, value in (
        ("FLASK_SECRET_KEY", secret_key),
        ("DB_HOST", "localhost"),
        ("DB_PORT", str(DB_CONFIG["port"])),
        ("DB_NAME", database),
        ("DB_USER", username),
        ("DB_PASSWORD", password),
    ):
        set_key(str(ENV_PATH), key, value)

    print("已建立網站專用 MySQL 帳號並驗證連線；密碼與網站金鑰只儲存在 .env。")
    print("網站帳號：", username)


if __name__ == "__main__":
    main()
