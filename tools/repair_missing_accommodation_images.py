"""Repair missing accommodation image paths using bundled static/images photos.

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
    "台北君悅酒店": "君悅酒店",
    "美麗信花園酒店": "美麗信",
    "酒內民宿（新北市民宿308號）官方LINE:@jeanettehome": "酒內民宿（新北市民宿308號）",
    "米窩-松山館Meworld Hotel - Songshan": "米窩-松山館",
    "艾捷天麗大飯店 Hej Taipei Arena Hotel": "艾捷天麗大飯店",
    "小穩居商旅 Hermitdorm 聖雄企業（入住時間最晚23點，當天超過時間不方便辦理入住）": "小穩居商旅 Hermitdorm",
    "雀客旅館 - 台北內湖": "雀客旅館",
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
        cursor.execute("SELECT accommodation_id, name, image_path FROM accommodations WHERE deleted_at IS NULL")
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
                unmatched.append({"accommodation_id": row["accommodation_id"], "name": name})
                continue
            updates.append({
                "accommodation_id": row["accommodation_id"],
                "name": name,
                "old_image_path": row["image_path"],
                "new_image_path": candidates[0].relative_to(STATIC_ROOT).as_posix(),
            })

        print(json.dumps({
            "total_accommodations": len(rows),
            "missing_images": len(missing),
            "matched": len(updates),
            "unmatched_count": len(unmatched),
            "unmatched": [] if args.summary else unmatched,
            "updates": [] if args.summary else updates,
        }, ensure_ascii=True, indent=2))

        if args.apply and updates:
            backup_dir = PROJECT_ROOT / "output"
            backup_dir.mkdir(exist_ok=True)
            backup_path = backup_dir / f"accommodation_image_paths_before_{datetime.now():%Y%m%d_%H%M%S}.json"
            backup_path.write_text(json.dumps(updates, ensure_ascii=False, indent=2), encoding="utf-8")
            try:
                for update in updates:
                    cursor.execute(
                        "UPDATE accommodations SET image_path = %s "
                        "WHERE accommodation_id = %s AND image_path <=> %s",
                        (update["new_image_path"], update["accommodation_id"], update["old_image_path"]),
                    )
                    if cursor.rowcount != 1:
                        raise RuntimeError(f"Accommodation {update['accommodation_id']} changed during repair")
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
