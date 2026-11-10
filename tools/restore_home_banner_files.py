"""Restore missing banner uploads from bundled images with matching titles.

Dry run by default; --apply copies files without changing database records.
"""

import argparse
from pathlib import Path
import shutil
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = PROJECT_ROOT / "static"
UPLOAD_ROOT = STATIC_ROOT / "uploads" / "banners"
sys.path.insert(0, str(PROJECT_ROOT))

from db import get_db_connection  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    connection = get_db_connection()
    if connection is None:
        raise SystemExit("Database connection failed")
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT banner_id, title, image_path FROM home_banners")
        rows = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

    restored = 0
    for row in rows:
        title = (row["title"] or "").strip()
        image_path = (row["image_path"] or "").replace("\\", "/")
        destination = (STATIC_ROOT / image_path).resolve()
        if not title or Path(title).name != title or "/" in title or "\\" in title:
            continue
        if not image_path.startswith("uploads/banners/"):
            continue
        try:
            destination.relative_to(UPLOAD_ROOT.resolve())
        except ValueError:
            continue
        if destination.is_file():
            continue
        source = STATIC_ROOT / "images" / f"{title}{destination.suffix.lower()}"
        if not source.is_file():
            print(f"NO_MATCH banner_id={row['banner_id']} title={title}")
            continue
        print(f"{'COPY' if args.apply else 'WOULD_COPY'} banner_id={row['banner_id']} {source.name} -> {image_path}")
        if args.apply:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        restored += 1
    print(f"{'RESTORED' if args.apply else 'MATCHED'}={restored}")


if __name__ == "__main__":
    main()
