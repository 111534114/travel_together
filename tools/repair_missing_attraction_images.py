"""Point attractions with missing uploads to matching, bundled static/images files.

Dry run by default. Use --apply after reviewing the proposed matches.
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
    "甜水鴛鴦湖|大埤頭": "甜水鴛鴦湖",
    "清香休閒農場、草莓、小蕃茄、草莓果醬DIY體驗、草莓盆移栽DIY）": "清香休閒農場",
    "白石畫廊 Whitestone Gallery": "白石畫廊",
}
sys.path.insert(0, str(PROJECT_ROOT))

from db import get_db_connection  # noqa: E402


def existing_image_path(raw_path):
    if not raw_path:
        return False
    candidate = (STATIC_ROOT / raw_path.replace("\\", "/")).resolve()
    try:
        candidate.relative_to(STATIC_ROOT.resolve())
    except ValueError:
        return False
    return candidate.is_file() and candidate.suffix.lower() in IMAGE_EXTENSIONS


def matching_images():
    by_name = defaultdict(list)
    for path in IMAGE_ROOT.iterdir():
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            by_name[path.stem.strip().casefold()].append(path)
    return by_name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write matched paths to the database")
    parser.add_argument("--summary", action="store_true", help="Print totals and unmatched names only")
    args = parser.parse_args()

    connection = get_db_connection()
    if connection is None:
        raise SystemExit("Database connection failed")
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT attraction_id, name, image_path FROM attractions WHERE deleted_at IS NULL"
        )
        rows = cursor.fetchall()
        images = matching_images()
        missing = [row for row in rows if not existing_image_path(row["image_path"])]
        updates = []
        unmatched_rows = []
        for row in missing:
            name = (row["name"] or "").strip()
            candidates = images.get(NAME_ALIASES.get(name, name).casefold(), [])
            if len(candidates) != 1:
                unmatched_rows.append({"attraction_id": row["attraction_id"], "name": row["name"]})
                continue
            updates.append({
                "attraction_id": row["attraction_id"],
                "name": row["name"],
                "old_image_path": row["image_path"],
                "new_image_path": candidates[0].relative_to(STATIC_ROOT).as_posix(),
            })

        print(json.dumps({
            "total_attractions": len(rows),
            "missing_images": len(missing),
            "exact_matches": len(updates),
            "unmatched": len(missing) - len(updates),
            "unmatched_rows": unmatched_rows,
            "matches": [] if args.summary else updates,
        }, ensure_ascii=True, indent=2))

        if args.apply and updates:
            backup_dir = PROJECT_ROOT / "output"
            backup_dir.mkdir(exist_ok=True)
            backup_path = backup_dir / f"attraction_image_paths_before_{datetime.now():%Y%m%d_%H%M%S}.json"
            backup_path.write_text(json.dumps(updates, ensure_ascii=False, indent=2), encoding="utf-8")
            try:
                for update in updates:
                    cursor.execute(
                        "UPDATE attractions SET image_path = %s "
                        "WHERE attraction_id = %s AND image_path <=> %s",
                        (update["new_image_path"], update["attraction_id"], update["old_image_path"]),
                    )
                    if cursor.rowcount != 1:
                        raise RuntimeError(f"Attraction {update['attraction_id']} changed during repair")
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
