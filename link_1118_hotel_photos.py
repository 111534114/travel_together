"""Link the 28 hotel photos from the November 18 archive to existing hotels.

Run without arguments to inspect matches; use --apply to update the database.
The previous image paths are saved to a JSON file in the system temp folder.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
import sys
import tempfile
from uuid import uuid4

import mysql.connector

from config import DB_CONFIG


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
PHOTO_NAMES = (
    "Grand Hyatt Taipei.jpg",
    "三德大飯店.jpg",
    "仲信大湖商旅.jpg",
    "凱撒趣淘漫旅 台北.jpg",
    "台北凱撒大飯店.jpg",
    "台北凱達大飯店.jpg",
    "台北國際飯店.jpg",
    "台北富信大飯店.jpg",
    "台北花園大酒店Taipei Garden Hotel.jpg",
    "台北馥敦飯店 復南館.jpg",
    "司旅 chez nous hotel.jpg",
    "喬合大飯店（香城連鎖）.jpg",
    "國聯大飯店.jpg",
    "大倉久和大飯店.jpg",
    "大新商旅.jpg",
    "德立莊 昆明館.jpg",
    "悦心旅.jpg",
    "承攜行旅 - 台北台大館.jpg",
    "捷絲旅 台北西門館.jpg",
    "松河璞旅 boutech hotel Waterfront.jpg",
    "皇家季節酒店台北南西館.jpg",
    "福容大飯店 台北二館.jpg",
    "米窩飯店-大安館 Meworld Hotel-Daan.jpg",
    "臺北文華東方酒店.jpg",
    "茹曦酒店 ILLUME TAIPEI.jpg",
    "豪悅大飯店(香城連鎖).jpg",
    "首都唯客樂飯店.jpg",
    "首都大飯店松山館.png",
)


def validate_photo(name):
    path = STATIC / "images" / name
    signature = path.read_bytes()[:12]
    if path.suffix.lower() == ".png":
        valid = signature.startswith(b"\x89PNG\r\n\x1a\n")
    else:
        valid = signature.startswith(b"\xff\xd8\xff")
    if not valid:
        raise ValueError(f"圖片格式不正確：{path}")


def old_image_exists(image_path):
    if not image_path:
        return False
    path = (STATIC / image_path.replace("\\", "/")).resolve()
    return path.is_relative_to(STATIC) and path.is_file()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="更新資料庫；預設只檢查")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    for name in PHOTO_NAMES:
        validate_photo(name)

    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)
    try:
        connection.start_transaction()
        placeholders = ",".join(["%s"] * len(PHOTO_NAMES))
        cursor.execute(
            "SELECT accommodation_id, name, image_path FROM accommodations "
            f"WHERE deleted_at IS NULL AND name IN ({placeholders}) FOR UPDATE",
            tuple(Path(name).stem for name in PHOTO_NAMES),
        )
        rows = cursor.fetchall()
        by_name = {row["name"]: row for row in rows}
        if len(rows) != len(PHOTO_NAMES) or len(by_name) != len(PHOTO_NAMES):
            raise ValueError(f"預期找到 {len(PHOTO_NAMES)} 間不同飯店，實際找到 {len(rows)} 筆；未更新資料庫")

        changes = []
        for name in PHOTO_NAMES:
            row = by_name[Path(name).stem]
            new_path = f"images/{name}"
            old_path = row["image_path"]
            if old_path == new_path:
                continue
            if old_image_exists(old_path):
                raise ValueError(f"「{row['name']}」現有圖片仍可使用，為避免覆蓋已更新的照片，未更新資料庫")
            changes.append({
                "accommodation_id": row["accommodation_id"],
                "name": row["name"],
                "old_image_path": old_path,
                "new_image_path": new_path,
            })

        print(f"照片 {len(PHOTO_NAMES)} 張；待更新 {len(changes)} 間；已連結 {len(PHOTO_NAMES) - len(changes)} 間")
        if not args.apply or not changes:
            connection.rollback()
            return

        backup_path = Path(tempfile.gettempdir()) / f"travel_together_hotel_photos_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:8]}.json"
        backup_path.write_text(json.dumps(changes, ensure_ascii=False, indent=2), encoding="utf-8")
        for change in changes:
            cursor.execute(
                "UPDATE accommodations SET image_path=%s "
                "WHERE accommodation_id=%s AND name=%s AND image_path <=> %s",
                (change["new_image_path"], change["accommodation_id"], change["name"], change["old_image_path"]),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(f"更新筆數不正確：{change['name']}")
        connection.commit()
        print(f"已更新 {len(changes)} 間飯店；原圖片路徑備份：{backup_path}")
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    main()
