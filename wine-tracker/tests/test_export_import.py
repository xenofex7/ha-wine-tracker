"""
Tests for the Export / Import feature.

Covers ZIP structure, manifest contents, CSV layout, image bundling
and behaviour with missing images / empty databases.
"""
import io
import json
import os
import sqlite3
import sys
import zipfile

import pytest

APP_DIR = os.path.join(os.path.dirname(__file__), "..", "app")
sys.path.insert(0, APP_DIR)

AJAX = {"X-Requested-With": "XMLHttpRequest"}


# ── Export: route + ZIP structure ─────────────────────────────────────────────

class TestExportRoute:
    def test_export_empty_db_returns_zip(self, client):
        """An empty database still yields a valid ZIP with manifest & empty wines."""
        resp = client.get("/export")
        assert resp.status_code == 200
        assert resp.mimetype == "application/zip"
        assert 'attachment' in resp.headers.get("Content-Disposition", "")

        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        names = set(zf.namelist())
        assert {"manifest.json", "wines.json", "wines.csv", "timeline.json"} <= names

    def test_export_filename_has_date(self, client):
        resp = client.get("/export")
        disposition = resp.headers["Content-Disposition"]
        assert "wine-tracker-export-" in disposition
        assert ".zip" in disposition

    def test_manifest_has_schema_and_counts(self, client, sample_wine):
        resp = client.get("/export")
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["schema_version"] == 1
        assert manifest["wine_count"] == 1
        assert "exported_at" in manifest
        assert "app_version" in manifest

    def test_wines_json_contains_sample_wine(self, client, sample_wine):
        resp = client.get("/export")
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        wines = json.loads(zf.read("wines.json"))
        assert len(wines) == 1
        w = wines[0]
        assert w["name"] == "Château Test"
        assert w["year"] == 2020
        assert w["grape"] == "Merlot"
        assert w["price"] == 29.9
        # All expected columns present on each record
        for col in ("id", "name", "vivino_id", "bottle_format", "notes"):
            assert col in w

    def test_csv_has_header_and_row(self, client, sample_wine):
        resp = client.get("/export")
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        csv_text = zf.read("wines.csv").decode()
        lines = csv_text.strip().splitlines()
        assert lines[0].startswith("name,year,type,region,grape")
        assert any("Château Test" in line for line in lines[1:])


# ── Export: image bundling ────────────────────────────────────────────────────

class TestExportImages:
    def _insert_wine_with_image(self, db, filename):
        """Insert a wine that references ``filename`` in the image column."""
        db.execute(
            "INSERT INTO wines (name, year, image) VALUES (?,?,?)",
            ("Imaged Wine", 2019, filename),
        )
        db.commit()

    def test_image_file_is_included(self, client, db, upload_dir):
        fname = "test-image.jpg"
        with open(os.path.join(upload_dir, fname), "wb") as f:
            f.write(b"\xFF\xD8\xFF\xE0" + b"0" * 100)  # tiny fake JPEG
        self._insert_wine_with_image(db, fname)

        resp = client.get("/export")
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        assert f"images/{fname}" in zf.namelist()
        # Content preserved
        assert zf.read(f"images/{fname}").startswith(b"\xFF\xD8\xFF\xE0")

    def test_missing_image_on_disk_is_skipped(self, client, db):
        """If the DB references an image that's not on disk, export still succeeds."""
        self._insert_wine_with_image(db, "missing.jpg")

        resp = client.get("/export")
        assert resp.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        assert "images/missing.jpg" not in zf.namelist()
        # The JSON still references it so the user can see what's gone
        wines = json.loads(zf.read("wines.json"))
        assert wines[0]["image"] == "missing.jpg"

    def test_duplicate_image_only_stored_once(self, client, db, upload_dir):
        fname = "shared.jpg"
        with open(os.path.join(upload_dir, fname), "wb") as f:
            f.write(b"data")
        db.execute("INSERT INTO wines (name, image) VALUES ('A', ?)", (fname,))
        db.execute("INSERT INTO wines (name, image) VALUES ('B', ?)", (fname,))
        db.commit()

        resp = client.get("/export")
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        image_entries = [n for n in zf.namelist() if n.startswith("images/")]
        assert image_entries == [f"images/{fname}"]


# ── Module-level helpers ──────────────────────────────────────────────────────

class TestModuleHelpers:
    def test_export_filename_format(self):
        from export_import import export_filename
        name = export_filename()
        assert name.startswith("wine-tracker-export-")
        assert name.endswith(".zip")
        # yyyy-mm-dd in the middle
        date_part = name[len("wine-tracker-export-"):-len(".zip")]
        assert len(date_part) == 10 and date_part.count("-") == 2

    def test_schema_version_is_int(self):
        from export_import import SCHEMA_VERSION
        assert isinstance(SCHEMA_VERSION, int)
        assert SCHEMA_VERSION >= 1
