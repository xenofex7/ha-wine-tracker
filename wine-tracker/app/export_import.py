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


# ── Import ────────────────────────────────────────────────────────────────────

class ImportError(Exception):
    """Raised when an uploaded archive / file cannot be parsed."""


# CSV column aliases (lower-cased headers accepted on import).
CSV_ALIASES = {
    "name": "name",
    "wine": "name",
    "year": "year",
    "vintage": "year",
    "jahrgang": "year",
    "type": "type",
    "typ": "type",
    "region": "region",
    "grape": "grape",
    "rebsorte": "grape",
    "quantity": "quantity",
    "menge": "quantity",
    "rating": "rating",
    "bewertung": "rating",
    "price": "price",
    "preis": "price",
    "purchased_at": "purchased_at",
    "gekauft": "purchased_at",
    "drink_from": "drink_from",
    "drink_until": "drink_until",
    "location": "location",
    "lager": "location",
    "bottle_format": "bottle_format",
    "notes": "notes",
    "notizen": "notes",
    "image": "image",
    "vivino_id": "vivino_id",
}


def _normalize_name(s) -> str:
    return (s or "").strip().lower()


def _coerce_int(v):
    if v is None or v == "":
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _coerce_float(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _normalize_wine(w: dict) -> dict:
    """Coerce types so a wine dict is ready to insert into SQLite."""
    out = {k: w.get(k) for k in WINE_COLUMNS if k != "id"}
    out["year"] = _coerce_int(out.get("year"))
    # Preserve 0 explicitly — only fall back when the value is truly missing.
    qty = _coerce_int(out.get("quantity"))
    out["quantity"] = qty if qty is not None else 1
    rating = _coerce_int(out.get("rating"))
    out["rating"] = rating if rating is not None else 0
    out["price"] = _coerce_float(out.get("price"))
    out["drink_from"] = _coerce_int(out.get("drink_from"))
    out["drink_until"] = _coerce_int(out.get("drink_until"))
    out["vivino_id"] = _coerce_int(out.get("vivino_id"))
    bf = _coerce_float(out.get("bottle_format"))
    out["bottle_format"] = bf if bf is not None else 0.75
    # Required column
    out["name"] = (out.get("name") or "").strip()
    return out


def _parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    wines: list[dict] = []
    for raw in reader:
        mapped: dict = {}
        for key, value in raw.items():
            if key is None:
                continue
            target = CSV_ALIASES.get(key.strip().lower())
            if target:
                mapped[target] = value.strip() if isinstance(value, str) else value
        if mapped.get("name"):
            wines.append(mapped)
    return wines


def parse_import_file(data: bytes, filename: str = "") -> dict:
    """Parse a ZIP or CSV payload into a normalized import structure.

    Returns a dict with keys:
        source          — "zip" or "csv"
        schema_version  — int (0 for CSV)
        wines           — list of normalized wine dicts (no id)
        timeline        — list of timeline entries (empty for CSV)
        images          — dict {filename: bytes}
        original_ids    — list of original wine ids, parallel to ``wines``
                          (used only for timeline re-linking on apply)
    """
    is_zip = data[:2] == b"PK" or filename.lower().endswith(".zip")
    if is_zip:
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as e:
            raise ImportError(f"Kein gültiges ZIP-Archiv: {e}")

        names = set(zf.namelist())
        if "wines.json" not in names:
            raise ImportError("wines.json fehlt im Archiv")

        try:
            manifest = json.loads(zf.read("manifest.json")) if "manifest.json" in names else {}
        except json.JSONDecodeError as e:
            raise ImportError(f"manifest.json ist kaputt: {e}")

        schema_version = int(manifest.get("schema_version", 1))
        if schema_version > SCHEMA_VERSION:
            raise ImportError(
                f"Archiv-Schema v{schema_version} ist neuer als unterstützt (v{SCHEMA_VERSION})."
            )

        try:
            raw_wines = json.loads(zf.read("wines.json"))
        except json.JSONDecodeError as e:
            raise ImportError(f"wines.json ist kaputt: {e}")

        if not isinstance(raw_wines, list):
            raise ImportError("wines.json muss eine Liste enthalten")

        timeline = []
        if "timeline.json" in names:
            try:
                timeline = json.loads(zf.read("timeline.json")) or []
            except json.JSONDecodeError:
                timeline = []

        images: dict[str, bytes] = {}
        for entry in names:
            if entry.startswith("images/") and not entry.endswith("/"):
                images[os.path.basename(entry)] = zf.read(entry)

        original_ids = [w.get("id") for w in raw_wines]
        wines = [_normalize_wine(w) for w in raw_wines]
        return {
            "source": "zip",
            "schema_version": schema_version,
            "wines": wines,
            "timeline": timeline,
            "images": images,
            "original_ids": original_ids,
        }

    # CSV fallback
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = data.decode("latin-1")
        except UnicodeDecodeError as e:
            raise ImportError(f"CSV-Datei konnte nicht gelesen werden: {e}")

    raw_wines = _parse_csv(text)
    if not raw_wines:
        raise ImportError("CSV enthält keine gültigen Weine (Spalte 'name' erforderlich)")
    wines = [_normalize_wine(w) for w in raw_wines]
    return {
        "source": "csv",
        "schema_version": 0,
        "wines": wines,
        "timeline": [],
        "images": {},
        "original_ids": [None] * len(wines),
    }


def match_wines(imported: list[dict], db) -> list[dict]:
    """Resolve each imported wine against existing rows.

    Match rule:
        1. ``vivino_id`` match (both sides non-null) → match
        2. else: case-insensitive ``name`` + exact ``year`` match

    Returns a list parallel to ``imported`` with items:
        {"matched": bool, "existing_id": int | None, "existing": dict | None}
    """
    existing = db.execute(
        "SELECT id, name, year, vivino_id FROM wines"
    ).fetchall()

    by_vivino: dict[int, dict] = {}
    by_name_year: dict[tuple[str, int | None], dict] = {}
    for row in existing:
        d = {"id": row["id"], "name": row["name"], "year": row["year"], "vivino_id": row["vivino_id"]}
        if d["vivino_id"]:
            by_vivino[d["vivino_id"]] = d
        by_name_year[(_normalize_name(d["name"]), d["year"])] = d

    results = []
    for w in imported:
        match = None
        vid = _coerce_int(w.get("vivino_id"))
        if vid and vid in by_vivino:
            match = by_vivino[vid]
        else:
            key = (_normalize_name(w.get("name")), _coerce_int(w.get("year")))
            match = by_name_year.get(key)
        results.append({
            "matched": match is not None,
            "existing_id": match["id"] if match else None,
            "existing": match,
        })
    return results


def apply_import(parsed: dict, matches: list[dict], db, upload_dir: str,
                 strategy: str = "skip") -> dict:
    """Apply a parsed import to the database.

    Parameters
    ----------
    strategy : str
        ``"skip"``  — keep existing duplicates, insert only new wines
        ``"overwrite"`` — update existing duplicates, insert new wines

    Returns a summary dict: ``{"inserted": N, "updated": N, "skipped": N}``.
    """
    if strategy not in ("skip", "overwrite"):
        raise ValueError(f"Unknown strategy: {strategy!r}")

    os.makedirs(upload_dir, exist_ok=True)

    # Write images first. If a filename already exists on disk we keep the
    # current file (images are content-addressed by UUID so collisions mean
    # "same image"). Missing images just mean the card will have no picture.
    for fname, blob in (parsed.get("images") or {}).items():
        dest = os.path.join(upload_dir, fname)
        if not os.path.isfile(dest):
            with open(dest, "wb") as f:
                f.write(blob)

    insert_cols = [c for c in WINE_COLUMNS if c != "id"]
    placeholders = ",".join(["?"] * len(insert_cols))
    update_sets = ",".join(f"{c}=?" for c in insert_cols)

    inserted = updated = skipped = 0
    id_map: dict[int, int] = {}  # original_id → new_id (for timeline)

    wines = parsed.get("wines") or []
    original_ids = parsed.get("original_ids") or [None] * len(wines)

    for wine, match, orig_id in zip(wines, matches, original_ids):
        values = [wine.get(c) for c in insert_cols]
        if match["matched"]:
            if strategy == "skip":
                skipped += 1
                if orig_id is not None:
                    id_map[orig_id] = match["existing_id"]
                continue
            db.execute(
                f"UPDATE wines SET {update_sets} WHERE id=?",
                values + [match["existing_id"]],
            )
            if orig_id is not None:
                id_map[orig_id] = match["existing_id"]
            updated += 1
        else:
            # Ensure `added` has a value for freshly inserted wines.
            if not wine.get("added"):
                idx = insert_cols.index("added")
                values[idx] = datetime.now().date().isoformat()
            cur = db.execute(
                f"INSERT INTO wines ({','.join(insert_cols)}) VALUES ({placeholders})",
                values,
            )
            if orig_id is not None:
                id_map[orig_id] = cur.lastrowid
            inserted += 1

    # Timeline is best-effort: only replay entries for wines that were freshly
    # inserted. Existing wines keep their current timeline untouched.
    timeline_entries = parsed.get("timeline") or []
    for entry in timeline_entries:
        orig = entry.get("wine_id")
        new_id = id_map.get(orig)
        if new_id is None:
            continue
        # Skip if this new_id already has any timeline (we only seed fresh ones)
        has_any = db.execute(
            "SELECT 1 FROM timeline WHERE wine_id=? LIMIT 1", (new_id,)
        ).fetchone()
        if has_any:
            continue
        db.execute(
            "INSERT INTO timeline (wine_id, action, quantity, timestamp) VALUES (?,?,?,?)",
            (new_id, entry.get("action") or "added",
             _coerce_int(entry.get("quantity")) or 1,
             entry.get("timestamp") or datetime.now().isoformat()),
        )

    db.commit()
    return {"inserted": inserted, "updated": updated, "skipped": skipped}
