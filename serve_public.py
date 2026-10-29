"""從這台桌機提供網站給隊員測試；只監聽本機，由 HTTPS tunnel 對外連入。"""

from config import DB_CONFIG, FLASK_SECRET_KEY, PUBLIC_BASE_URL


def validate_public_settings():
    if len(FLASK_SECRET_KEY) < 32:
        raise SystemExit("請先在 .env 設定至少 32 字元的 FLASK_SECRET_KEY。")
    if DB_CONFIG["user"].lower() == "root" or not DB_CONFIG["password"]:
        raise SystemExit("請先建立非 root 的 MySQL 專用帳號，並在 .env 設定 DB_USER、DB_PASSWORD。")
    if not PUBLIC_BASE_URL.startswith("https://"):
        raise SystemExit("請先在 .env 將 PUBLIC_BASE_URL 設為公開的 HTTPS 網址。")


if __name__ == "__main__":
    validate_public_settings()

    from waitress import serve

    from app import app
    from db import get_db_connection
    import trip_reminders

    connection = get_db_connection()
    if connection is None:
        raise SystemExit("無法用 .env 中的資料庫設定連線；網站尚未對外啟動。")
    connection.close()

    trip_reminders.start_scheduler()
    serve(app, host="127.0.0.1", port=5000)
