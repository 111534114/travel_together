"""Repair missing restaurant image paths using bundled static/images photos.

Dry run by default. --apply saves the old database paths before updating.
"""

import argparse
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = PROJECT_ROOT / "static"
IMAGE_ROOT = STATIC_ROOT / "images"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
NAME_ALIASES = {
    "布納咖啡館 內湖館": "布納咖啡館",
    "mama says yes 大馬人 | 內湖本店": "mama says yes 大馬人",
    "WilsonPark 威爾森公園 （Steak & Wine）": "WilsonPark 威爾森公園",
    "陳三Chen*3 Bistro": "陳三Chen",
    "銀象雲泰美食館 Thai food（內湖店 ）": "銀象雲泰美食館 Thai food",
    "麻膳堂 MAZENDO （內湖舊宗店）": "麻膳堂 MAZENDO",
}
sys.path.insert(0, str(PROJECT_ROOT))

from db import get_db_connection  # noqa: E402


def existing_image_path(raw_path):
    if not raw_path:
        return False
    path = (STATIC_ROOT / raw_path.replace("\\", "/")).resolve()
    try:
        path.relative_to(STATIC_ROOT.resolve())
    except ValueError:
        return False
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    connection = get_db_connection()
    if connection is None:
        raise SystemExit("Database connection failed")
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT restaurant_id, name, image_path FROM restaurants WHERE deleted_at IS NULL")
        rows = cursor.fetchall()
        images = defaultdict(list)
        for path in IMAGE_ROOT.iterdir():
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                images[path.stem.strip().casefold()].append(path)

        missing = [row for row in rows if not existing_image_path(row["image_path"])]
        updates = []
        unmatched = []
        for row in missing:
            name = (row["name"] or "").strip()
            candidates = images.get(NAME_ALIASES.get(name, name).casefold(), [])
            if len(candidates) != 1:
                unmatched.append({"restaurant_id": row["restaurant_id"], "name": name})
                continue
            updates.append({
                "restaurant_id": row["restaurant_id"],
                "name": name,
                "old_image_path": row["image_path"],
                "new_image_path": candidates[0].relative_to(STATIC_ROOT).as_posix(),
            })

        print(json.dumps({
            "total_restaurants": len(rows),
            "missing_images": len(missing),
            "matched": len(updates),
            "unmatched": unmatched,
            "updates": [] if args.summary else updates,
        }, ensure_ascii=True, indent=2))

        if args.apply and updates:
            backup_dir = PROJECT_ROOT / "output"
            backup_dir.mkdir(exist_ok=True)
            backup_path = backup_dir / f"restaurant_image_paths_before_{datetime.now():%Y%m%d_%H%M%S}.json"
            backup_path.write_text(json.dumps(updates, ensure_ascii=False, indent=2), encoding="utf-8")
            try:
                for update in updates:
                    cursor.execute(
                        "UPDATE restaurants SET image_path = %s "
                        "WHERE restaurant_id = %s AND image_path <=> %s",
                        (update["new_image_path"], update["restaurant_id"], update["old_image_path"]),
                    )
                    if cursor.rowcount != 1:
                        raise RuntimeError(f"Restaurant {update['restaurant_id']} changed during repair")
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            print(f"UPDATED={len(updates)} BACKUP={backup_path}")
    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    main()
