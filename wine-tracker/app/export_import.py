"""
Export / Import for Wine Tracker.

Export format: a ZIP archive containing
    manifest.json   — schema version, timestamp, counts
    wines.json      — authoritative wine data (all DB columns)
    wines.csv       — flat, human-readable view (for spreadsheet apps)
    timeline.json   — timeline entries (referenced by original wine id)
    images/         — original image files (filenames match `image` column)

The JSON is the source of truth on re-import; the CSV is informational
so the standard user can open the archive in Excel / Numbers / Sheets.
"""

from __future__ import annotations

import csv
import io
import json
import os
import zipfile
from datetime import datetime, timezone
from typing import Iterable


# Bumped when the export format changes in a backwards-incompatible way.
SCHEMA_VERSION = 1

# Columns exported from the `wines` table. Order matches the CSV header.
# `id` is included for timeline cross-reference but ignored on import.
WINE_COLUMNS = [
    "id",
    "name",
    "year",
    "type",
    "region",
    "quantity",
    "rating",
    "notes",
    "image",
    "added",
    "purchased_at",
    "price",
    "drink_from",
    "drink_until",
    "location",
    "grape",
    "vivino_id",
    "bottle_format",
    "maturity_data",
    "taste_profile",
    "food_pairings",
]

# A subset of columns presented in the CSV for readability. The JSON
# remains the full / authoritative copy.
CSV_COLUMNS = [
    "name",
    "year",
    "type",
    "region",
    "grape",
    "quantity",
    "rating",
    "price",
    "purchased_at",
    "drink_from",
    "drink_until",
    "location",
    "bottle_format",
    "notes",
    "image",
    "vivino_id",
]


def _row_to_dict(row) -> dict:
    """Convert a sqlite3.Row (or dict-like) to a plain dict of exported fields."""
    return {col: row[col] if col in row.keys() else None for col in WINE_COLUMNS}


def _wines_to_csv(wines: Iterable[dict]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for w in wines:
        writer.writerow({k: (w.get(k) if w.get(k) is not None else "") for k in CSV_COLUMNS})
    return buf.getvalue()


def build_export_zip(db, upload_dir: str, app_version: str = "") -> bytes:
    """Build the export ZIP in memory and return its bytes.

    Parameters
    ----------
    db : sqlite3.Connection
        Connection with ``row_factory = sqlite3.Row``.
    upload_dir : str
        Absolute path to the uploads folder (images are copied from here).
    app_version : str
        Optional app version string for the manifest.
    """
    wine_rows = db.execute(
        "SELECT " + ", ".join(WINE_COLUMNS) + " FROM wines ORDER BY id"
    ).fetchall()
    wines = [_row_to_dict(r) for r in wine_rows]

    try:
        timeline_rows = db.execute(
            "SELECT wine_id, action, quantity, timestamp FROM timeline ORDER BY id"
        ).fetchall()
        timeline = [dict(r) for r in timeline_rows]
    except Exception:
        # Older DBs may not have the timeline table.
        timeline = []

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "app_version": app_version,
        "wine_count": len(wines),
        "timeline_count": len(timeline),
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        zf.writestr("wines.json", json.dumps(wines, indent=2, ensure_ascii=False, default=str))
        zf.writestr("timeline.json", json.dumps(timeline, indent=2, ensure_ascii=False, default=str))
        zf.writestr("wines.csv", _wines_to_csv(wines))

        # Deduplicate image filenames so we don't add the same file twice.
        seen: set[str] = set()
        for w in wines:
            img = w.get("image")
            if not img or img in seen:
                continue
            seen.add(img)
            src = os.path.join(upload_dir, img)
            if os.path.isfile(src):
                zf.write(src, arcname=f"images/{img}")
            # Missing images are silently skipped — the JSON still references
            # the filename so the user sees what's missing after a restore.

    return buf.getvalue()


def export_filename(now: datetime | None = None) -> str:
    """Return the suggested download filename, e.g. ``wine-tracker-2026-04-17.zip``."""
    ts = (now or datetime.now()).strftime("%Y-%m-%d")
    return f"wine-tracker-export-{ts}.zip"
