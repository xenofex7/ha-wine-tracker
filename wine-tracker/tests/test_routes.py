"""
Tests for Flask routes — CRUD operations on wines.
All requests use AJAX headers to get JSON responses.
"""
import io
import json
import os
import sys

import pytest

APP_DIR = os.path.join(os.path.dirname(__file__), "..", "app")
sys.path.insert(0, APP_DIR)

AJAX = {"X-Requested-With": "XMLHttpRequest"}


# ── GET / (index) ─────────────────────────────────────────────────────────────

class TestIndex:
    def test_index_loads(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_index_contains_wine_tracker(self, client):
        resp = client.get("/")
        assert b"Wine Tracker" in resp.data or b"wine" in resp.data.lower()

    def test_search_filter(self, client, sample_wine):
        resp = client.get("/?q=Château")
        assert resp.status_code == 200
        assert b"teau Test" in resp.data

    def test_search_no_results(self, client, sample_wine):
        resp = client.get("/?q=NonexistentWine12345")
        assert resp.status_code == 200

    def test_type_filter(self, client, sample_wine):
        resp = client.get("/?type=Rotwein")
        assert resp.status_code == 200

    def test_hide_empty_bottles(self, client):
        """show_empty=0 should hide wines with quantity=0."""
        # Add a wine with quantity 0
        client.post("/add", data={"name": "Empty Wine", "quantity": "0"}, headers=AJAX)
        client.post("/add", data={"name": "Full Wine", "quantity": "5"}, headers=AJAX)
        resp = client.get("/?show_empty=0")
        assert b"Full Wine" in resp.data
        assert b"Empty Wine" not in resp.data


# ── POST /add ─────────────────────────────────────────────────────────────────

class TestAddWine:
    def test_add_wine_ajax(self, client):
        resp = client.post(
            "/add",
            data={"name": "Testvin", "year": "2021", "type": "Weisswein", "quantity": "2"},
            headers=AJAX,
        )
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert data["wine"]["name"] == "Testvin"
        assert data["wine"]["year"] == 2021
        assert data["wine"]["type"] == "Weisswein"
        assert data["wine"]["quantity"] == 2

    def test_add_wine_redirect(self, client):
        """Non-AJAX add should redirect."""
        resp = client.post(
            "/add",
            data={"name": "Redirect Wine", "quantity": "1"},
        )
        assert resp.status_code == 302

    def test_add_wine_minimal(self, client):
        """Only name is required."""
        resp = client.post("/add", data={"name": "Minimal"}, headers=AJAX)
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert data["wine"]["name"] == "Minimal"
        assert data["wine"]["quantity"] == 1  # default

    def test_add_wine_with_price(self, client):
        resp = client.post(
            "/add",
            data={"name": "Priced Wine", "price": "49.50"},
            headers=AJAX,
        )
        data = json.loads(resp.data)
        assert data["wine"]["price"] == 49.50

    def test_add_wine_with_bottle_format(self, client):
        resp = client.post(
            "/add",
            data={"name": "Magnum", "bottle_format": "1.5", "quantity": "1"},
            headers=AJAX,
        )
        data = json.loads(resp.data)
        assert data["wine"]["bottle_format"] == 1.5

    def test_add_wine_default_bottle_format(self, client):
        resp = client.post(
            "/add",
            data={"name": "Standard Bottle"},
            headers=AJAX,
        )
        data = json.loads(resp.data)
        assert data["wine"]["bottle_format"] == 0.75

    def test_add_wine_with_vivino_id(self, client):
        resp = client.post(
            "/add",
            data={"name": "Vivino Wine", "vivino_id": "12345"},
            headers=AJAX,
        )
        data = json.loads(resp.data)
        assert data["wine"]["vivino_id"] == 12345

    def test_add_wine_updates_stats(self, client):
        resp = client.post(
            "/add",
            data={"name": "Stats Wine", "quantity": "5"},
            headers=AJAX,
        )
        data = json.loads(resp.data)
        assert data["stats"]["total"] == 5

    def test_add_wine_with_image(self, client, upload_dir):
        """Upload a fake image file."""
        fake_image = (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100), "label.png")
        resp = client.post(
            "/add",
            data={"name": "Photo Wine", "image": fake_image},
            headers=AJAX,
            content_type="multipart/form-data",
        )
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert data["wine"]["image"] is not None
        assert data["wine"]["image"].endswith(".png")
        # File should exist on disk
        assert os.path.isfile(os.path.join(upload_dir, data["wine"]["image"]))


# ── POST /edit/<id> ───────────────────────────────────────────────────────────

class TestEditWine:
    def test_edit_wine(self, client, sample_wine):
        wine_id = sample_wine["wine"]["id"]
        resp = client.post(
            f"/edit/{wine_id}",
            data={
                "name": "Château Edited",
                "year": "2021",
                "type": "Weisswein",
                "quantity": "10",
                "rating": "5",
                "region": "Loire, FR",
                "notes": "Updated",
                "grape": "Chardonnay",
                "bottle_format": "1.5",
            },
            headers=AJAX,
        )
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert data["wine"]["name"] == "Château Edited"
        assert data["wine"]["year"] == 2021
        assert data["wine"]["type"] == "Weisswein"
        assert data["wine"]["quantity"] == 10
        assert data["wine"]["rating"] == 5
        assert data["wine"]["grape"] == "Chardonnay"
        assert data["wine"]["bottle_format"] == 1.5

    def test_edit_nonexistent_wine(self, client):
        resp = client.post(
            "/edit/99999",
            data={"name": "Ghost"},
            headers=AJAX,
        )
        # Should redirect (wine not found)
        assert resp.status_code == 302

    def test_edit_updates_stats(self, client, sample_wine):
        wine_id = sample_wine["wine"]["id"]
        resp = client.post(
            f"/edit/{wine_id}",
            data={"name": "Stats Edit", "quantity": "20"},
            headers=AJAX,
        )
        data = json.loads(resp.data)
        assert data["stats"]["total"] == 20

    def test_edit_delete_image(self, client, upload_dir):
        """Editing with delete_image=1 should remove the image."""
        # First add wine with image
        fake_image = (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100), "label.png")
        resp = client.post(
            "/add",
            data={"name": "Delete Image Wine", "image": fake_image},
            headers=AJAX,
            content_type="multipart/form-data",
        )
        wine = json.loads(resp.data)["wine"]
        assert wine["image"] is not None
        img_path = os.path.join(upload_dir, wine["image"])
        assert os.path.isfile(img_path)

        # Now edit with delete_image
        resp = client.post(
            f"/edit/{wine['id']}",
            data={"name": "Delete Image Wine", "delete_image": "1"},
            headers=AJAX,
        )
        data = json.loads(resp.data)
        assert data["wine"]["image"] is None
        assert not os.path.isfile(img_path)


# ── POST /duplicate/<id> ─────────────────────────────────────────────────────

class TestDuplicateWine:
    def test_duplicate_wine(self, client, sample_wine):
        wine_id = sample_wine["wine"]["id"]
        resp = client.post(
            f"/duplicate/{wine_id}",
            data={"new_year": "2021", "quantity": "6"},
            headers=AJAX,
        )
        data = json.loads(resp.data)
        assert data["ok"] is True
        new_wine = data["wine"]
        assert new_wine["name"] == "Château Test"
        assert new_wine["year"] == 2021  # changed
        assert new_wine["quantity"] == 6  # changed
        assert new_wine["region"] == "Bordeaux, FR"  # copied
        assert new_wine["grape"] == "Merlot"  # copied
        assert new_wine["id"] != wine_id  # new ID

    def test_duplicate_nonexistent_wine(self, client):
        resp = client.post("/duplicate/99999", data={}, headers=AJAX)
        assert resp.status_code == 302

    def test_duplicate_preserves_bottle_format(self, client):
        """Duplicated wine should keep the bottle format."""
        # Add magnum
        resp = client.post(
            "/add",
            data={"name": "Magnum", "bottle_format": "1.5", "quantity": "1"},
            headers=AJAX,
        )
        wine_id = json.loads(resp.data)["wine"]["id"]

        # Duplicate
        resp = client.post(f"/duplicate/{wine_id}", data={}, headers=AJAX)
        data = json.loads(resp.data)
        assert data["wine"]["bottle_format"] == 1.5


# ── POST /delete/<id> ────────────────────────────────────────────────────────

class TestDeleteWine:
    def test_delete_wine(self, client, sample_wine):
        wine_id = sample_wine["wine"]["id"]
        resp = client.post(f"/delete/{wine_id}", headers=AJAX)
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert data["deleted"] == wine_id
        assert data["stats"]["total"] == 0

    def test_delete_nonexistent_wine(self, client):
        resp = client.post("/delete/99999", headers=AJAX)
        data = json.loads(resp.data)
        assert data["ok"] is True  # Still returns ok (idempotent)

    def test_delete_removes_orphan_image(self, client, upload_dir):
        """Deleting a wine should remove its image if no other wine uses it."""
        fake_image = (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100), "label.png")
        resp = client.post(
            "/add",
            data={"name": "Delete Me", "image": fake_image},
            headers=AJAX,
            content_type="multipart/form-data",
        )
        wine = json.loads(resp.data)["wine"]
        img_path = os.path.join(upload_dir, wine["image"])
        assert os.path.isfile(img_path)

        client.post(f"/delete/{wine['id']}", headers=AJAX)
        assert not os.path.isfile(img_path)


# ── GET /stats ────────────────────────────────────────────────────────────────

class TestStatsPage:
    def test_stats_loads_empty(self, client):
        resp = client.get("/stats")
        assert resp.status_code == 200

    def test_stats_with_data(self, client, sample_wine):
        resp = client.get("/stats")
        assert resp.status_code == 200
        # Should contain stat labels
        assert b"Rotwein" in resp.data or b"Red" in resp.data

    def test_stats_total_liters(self, client):
        """Total liters should be calculated from quantity * bottle_format."""
        # Add 2x standard (0.75L) + 1x magnum (1.5L)
        client.post("/add", data={"name": "Standard", "quantity": "2", "bottle_format": "0.75"}, headers=AJAX)
        client.post("/add", data={"name": "Magnum", "quantity": "1", "bottle_format": "1.5"}, headers=AJAX)

        resp = client.get("/stats")
        assert resp.status_code == 200
        # 2*0.75 + 1*1.5 = 3.0 liters
        assert b"3.0" in resp.data


# ── GET /api/summary ──────────────────────────────────────────────────────────

class TestApiSummary:
    def test_empty_cellar(self, client):
        resp = client.get("/api/summary")
        data = json.loads(resp.data)
        assert data["total_bottles"] == 0
        assert data["by_type"] == []

    def test_with_wines(self, client, sample_wine):
        resp = client.get("/api/summary")
        data = json.loads(resp.data)
        assert data["total_bottles"] == 3
        assert len(data["by_type"]) == 1
        assert data["by_type"][0]["type"] == "Rotwein"

    def test_multiple_types(self, client):
        client.post("/add", data={"name": "Red", "type": "Rotwein", "quantity": "2"}, headers=AJAX)
        client.post("/add", data={"name": "White", "type": "Weisswein", "quantity": "3"}, headers=AJAX)
        resp = client.get("/api/summary")
        data = json.loads(resp.data)
        assert data["total_bottles"] == 5
        assert len(data["by_type"]) == 2
