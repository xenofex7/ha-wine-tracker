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


# ── Import: parsing ───────────────────────────────────────────────────────────

class TestImportParsing:
    def test_parse_zip_returns_wines(self, client, sample_wine):
        """Build an export, feed it into parse_import_file, get the wine back."""
        from export_import import parse_import_file

        resp = client.get("/export")
        parsed = parse_import_file(resp.data, filename="backup.zip")
        assert parsed["source"] == "zip"
        assert parsed["schema_version"] == 1
        assert len(parsed["wines"]) == 1
        assert parsed["wines"][0]["name"] == "Château Test"

    def test_parse_corrupt_zip_raises(self):
        from export_import import parse_import_file, ImportError
        with pytest.raises(ImportError):
            parse_import_file(b"not a zip at all", filename="broken.zip")

    def test_parse_future_schema_version_rejected(self):
        import zipfile as zf_mod
        from export_import import parse_import_file, ImportError

        buf = io.BytesIO()
        with zf_mod.ZipFile(buf, "w") as zf:
            zf.writestr("manifest.json", json.dumps({"schema_version": 999}))
            zf.writestr("wines.json", json.dumps([]))
        with pytest.raises(ImportError, match="neuer als unterstützt"):
            parse_import_file(buf.getvalue(), filename="future.zip")

    def test_parse_csv_basic(self):
        from export_import import parse_import_file
        csv_bytes = b"name,year,grape\nMerlot Test,2019,Merlot\n"
        parsed = parse_import_file(csv_bytes, filename="wines.csv")
        assert parsed["source"] == "csv"
        assert len(parsed["wines"]) == 1
        assert parsed["wines"][0]["name"] == "Merlot Test"
        assert parsed["wines"][0]["year"] == 2019
        assert parsed["wines"][0]["grape"] == "Merlot"

    def test_parse_csv_german_headers(self):
        from export_import import parse_import_file
        csv_bytes = "jahrgang,name,rebsorte\n2020,Riesling Spät,Riesling\n".encode()
        parsed = parse_import_file(csv_bytes, filename="de.csv")
        assert parsed["wines"][0]["name"] == "Riesling Spät"
        assert parsed["wines"][0]["year"] == 2020
        assert parsed["wines"][0]["grape"] == "Riesling"

    def test_parse_csv_without_name_raises(self):
        from export_import import parse_import_file, ImportError
        with pytest.raises(ImportError):
            parse_import_file(b"year,grape\n2020,Merlot\n", filename="bad.csv")

    def test_quantity_zero_preserved(self):
        """Regression: quantity=0 must not be rewritten to 1 on import."""
        from export_import import parse_import_file
        csv_bytes = b"name,year,quantity,rating\nEmpty Bottle,2018,0,0\n"
        parsed = parse_import_file(csv_bytes, filename="zero.csv")
        assert parsed["wines"][0]["quantity"] == 0
        assert parsed["wines"][0]["rating"] == 0

    def test_roundtrip_preserves_zero_quantity(self, client, db, sample_wine):
        """Exporting and re-importing a zero-qty wine keeps it at zero."""
        wine_id = sample_wine["wine"]["id"]
        db.execute("UPDATE wines SET quantity=0 WHERE id=?", (wine_id,))
        db.commit()

        zip_bytes = client.get("/export").data
        db.execute("DELETE FROM wines")
        db.execute("DELETE FROM timeline")
        db.commit()

        preview = client.post(
            "/import/preview",
            data={"file": (io.BytesIO(zip_bytes), "b.zip")},
            content_type="multipart/form-data",
        )
        token = json.loads(preview.data)["token"]
        client.post(
            "/import/commit",
            data=json.dumps({"token": token, "strategy": "skip"}),
            content_type="application/json",
        )

        row = db.execute("SELECT quantity FROM wines").fetchone()
        assert row["quantity"] == 0


# ── Import: duplicate matching ────────────────────────────────────────────────

class TestMatchWines:
    def test_vivino_id_match(self, client, db):
        from export_import import match_wines
        db.execute("INSERT INTO wines (name, year, vivino_id) VALUES ('A',2020,42)")
        db.commit()
        matches = match_wines(
            [{"name": "Completely Different", "year": 1999, "vivino_id": 42}],
            db,
        )
        assert matches[0]["matched"] is True
        assert matches[0]["existing"]["name"] == "A"

    def test_name_year_match_case_insensitive(self, client, db):
        from export_import import match_wines
        db.execute("INSERT INTO wines (name, year) VALUES ('Barolo',2018)")
        db.commit()
        matches = match_wines(
            [{"name": "  BAROLO ", "year": 2018, "vivino_id": None}],
            db,
        )
        assert matches[0]["matched"] is True

    def test_no_match(self, client, db):
        from export_import import match_wines
        db.execute("INSERT INTO wines (name, year) VALUES ('Barolo',2018)")
        db.commit()
        matches = match_wines(
            [{"name": "Barolo", "year": 2019, "vivino_id": None}],
            db,
        )
        assert matches[0]["matched"] is False


# ── Import: /import/preview + /import/commit round-trip ───────────────────────

class TestImportRoutes:
    def _upload(self, client, data, filename):
        return client.post(
            "/import/preview",
            data={"file": (io.BytesIO(data), filename)},
            content_type="multipart/form-data",
        )

    def test_preview_rejects_empty(self, client):
        resp = client.post(
            "/import/preview",
            data={"file": (io.BytesIO(b""), "e.zip")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_preview_rejects_garbage(self, client):
        resp = self._upload(client, b"garbage bytes", "x.zip")
        assert resp.status_code == 400
        body = json.loads(resp.data)
        assert body["ok"] is False

    def test_preview_returns_counts_and_token(self, client, sample_wine):
        """Exporting and re-previewing yields one duplicate (the sample wine)."""
        zip_bytes = client.get("/export").data
        resp = self._upload(client, zip_bytes, "backup.zip")
        assert resp.status_code == 200
        body = json.loads(resp.data)
        assert body["ok"] is True
        assert body["token"]
        assert body["counts"]["total"] == 1
        assert body["counts"]["duplicates"] == 1
        assert body["counts"]["new"] == 0

    def test_commit_skip_keeps_existing(self, client, db, sample_wine):
        zip_bytes = client.get("/export").data
        preview = json.loads(self._upload(client, zip_bytes, "b.zip").data)
        resp = client.post(
            "/import/commit",
            data=json.dumps({"token": preview["token"], "strategy": "skip"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        body = json.loads(resp.data)
        assert body["ok"] is True
        assert body["skipped"] == 1
        assert body["inserted"] == 0
        # Still just one wine in DB
        count = db.execute("SELECT COUNT(*) AS c FROM wines").fetchone()["c"]
        assert count == 1

    def test_commit_overwrite_updates_existing(self, client, db, sample_wine):
        """Export, mutate the JSON notes, re-import with overwrite."""
        import zipfile as zf_mod
        zip_bytes = client.get("/export").data
        zin = zf_mod.ZipFile(io.BytesIO(zip_bytes))
        wines = json.loads(zin.read("wines.json"))
        wines[0]["notes"] = "OVERWRITTEN"

        buf = io.BytesIO()
        with zf_mod.ZipFile(buf, "w") as zout:
            for name in zin.namelist():
                if name == "wines.json":
                    zout.writestr("wines.json", json.dumps(wines))
                else:
                    zout.writestr(name, zin.read(name))

        preview = json.loads(self._upload(client, buf.getvalue(), "m.zip").data)
        resp = client.post(
            "/import/commit",
            data=json.dumps({"token": preview["token"], "strategy": "overwrite"}),
            content_type="application/json",
        )
        body = json.loads(resp.data)
        assert body["ok"] is True
        assert body["updated"] == 1
        row = db.execute("SELECT notes FROM wines").fetchone()
        assert row["notes"] == "OVERWRITTEN"

    def test_commit_inserts_fresh_wine_from_csv(self, client, db):
        csv_bytes = b"name,year,grape\nNebbiolo Import,2015,Nebbiolo\n"
        preview = json.loads(self._upload(client, csv_bytes, "new.csv").data)
        assert preview["counts"]["new"] == 1
        resp = client.post(
            "/import/commit",
            data=json.dumps({"token": preview["token"], "strategy": "skip"}),
            content_type="application/json",
        )
        body = json.loads(resp.data)
        assert body["inserted"] == 1
        row = db.execute("SELECT name, year FROM wines").fetchone()
        assert row["name"] == "Nebbiolo Import"
        assert row["year"] == 2015

    def test_commit_rejects_invalid_token(self, client):
        resp = client.post(
            "/import/commit",
            data=json.dumps({"token": "../etc/passwd", "strategy": "skip"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_commit_rejects_missing_token(self, client):
        resp = client.post(
            "/import/commit",
            data=json.dumps({"token": "doesnotexist123", "strategy": "skip"}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_commit_rejects_bad_strategy(self, client, sample_wine):
        zip_bytes = client.get("/export").data
        preview = json.loads(self._upload(client, zip_bytes, "b.zip").data)
        resp = client.post(
            "/import/commit",
            data=json.dumps({"token": preview["token"], "strategy": "destroy-all"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_roundtrip_wine_is_identical(self, client, db, upload_dir, sample_wine):
        """Full roundtrip: export → delete all → import → data matches."""
        # Snapshot the original
        original = db.execute("SELECT * FROM wines").fetchone()
        zip_bytes = client.get("/export").data

        # Wipe wines
        db.execute("DELETE FROM wines")
        db.execute("DELETE FROM timeline")
        db.commit()
        assert db.execute("SELECT COUNT(*) AS c FROM wines").fetchone()["c"] == 0

        preview = json.loads(self._upload(client, zip_bytes, "b.zip").data)
        client.post(
            "/import/commit",
            data=json.dumps({"token": preview["token"], "strategy": "skip"}),
            content_type="application/json",
        )

        restored = db.execute("SELECT * FROM wines").fetchone()
        for col in ("name", "year", "type", "region", "grape", "rating",
                    "quantity", "price", "location", "bottle_format"):
            assert restored[col] == original[col], f"mismatch on {col}"

    def test_image_is_restored_on_import(self, client, db, upload_dir):
        """Image file inside the ZIP is written into the uploads folder."""
        import zipfile as zf_mod
        img_name = "restored-img.jpg"
        img_bytes = b"\xFF\xD8\xFFFAKEJPEG"

        buf = io.BytesIO()
        with zf_mod.ZipFile(buf, "w") as zf:
            zf.writestr("manifest.json", json.dumps({"schema_version": 1}))
            zf.writestr("wines.json", json.dumps([{
                "name": "Imaged",
                "year": 2021,
                "image": img_name,
            }]))
            zf.writestr(f"images/{img_name}", img_bytes)

        preview = json.loads(self._upload(client, buf.getvalue(), "i.zip").data)
        client.post(
            "/import/commit",
            data=json.dumps({"token": preview["token"], "strategy": "skip"}),
            content_type="application/json",
        )

        dest = os.path.join(upload_dir, img_name)
        assert os.path.isfile(dest)
        with open(dest, "rb") as f:
            assert f.read() == img_bytes


# ── Auth: readonly user blocked ───────────────────────────────────────────────

class TestImportAuth:
    def test_readonly_blocked_from_preview(self, client, monkeypatch):
        import app as wine_app
        monkeypatch.setattr(wine_app, "AUTH_ENABLED", True)
        with client.session_transaction() as s:
            s["user"] = "viewer"
            s["role"] = "readonly"
        resp = client.post(
            "/import/preview",
            data={"file": (io.BytesIO(b"x"), "x.csv")},
            content_type="multipart/form-data",
            headers=AJAX,
        )
        assert resp.status_code == 403

    def test_readonly_blocked_from_commit(self, client, monkeypatch):
        import app as wine_app
        monkeypatch.setattr(wine_app, "AUTH_ENABLED", True)
        with client.session_transaction() as s:
            s["user"] = "viewer"
            s["role"] = "readonly"
        resp = client.post(
            "/import/commit",
            data=json.dumps({"token": "abc", "strategy": "skip"}),
            content_type="application/json",
        )
        assert resp.status_code == 403
