"""
Tests for Flask routes — CRUD operations on wines.
All requests use AJAX headers to get JSON responses.
"""
import io
import json
import os
import sys

import pytest
from unittest.mock import patch
from werkzeug.security import generate_password_hash

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

    def test_edit_param_loads(self, client, sample_wine):
        """Index with ?edit=ID should load successfully (JS opens modal client-side)."""
        wine_id = sample_wine["wine"]["id"]
        resp = client.get(f"/?edit={wine_id}")
        assert resp.status_code == 200
        # The wine card should be present for JS to find
        assert str(wine_id).encode() in resp.data

    def test_view_modal_opens_in_place(self, client, sample_wine):
        """View modal JS (openViewModal) should be present on index page."""
        resp = client.get("/")
        assert b'openViewModal' in resp.data

    def test_type_filter(self, client, sample_wine):
        resp = client.get("/?type=Rotwein")
        assert resp.status_code == 200

    def test_about_section_with_version(self, client):
        """Settings modal should contain About section with app version."""
        resp = client.get("/")
        html = resp.data.decode()
        assert "v1.5.0" in html
        assert "settings_about" in html or "Über" in html

    def test_view_modal_present(self, client):
        """Index page should contain the viewModal overlay."""
        resp = client.get("/")
        assert b'id="viewModal"' in resp.data

    def test_card_body_calls_view(self, client, sample_wine):
        """Card body onclick should call viewFromCard."""
        resp = client.get("/")
        assert b'viewFromCard(this)' in resp.data

    def test_pencil_still_calls_edit(self, client, sample_wine):
        """Pencil button should still call editFromCard."""
        resp = client.get("/")
        assert b'editFromCard(this)' in resp.data

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

    def test_stats_tooltip_data_contains_wine_id(self, client, sample_wine):
        """WINE_DATA in stats page should include wine IDs for clickable tooltips."""
        wine_id = sample_wine["wine"]["id"]
        resp = client.get("/stats")
        html = resp.data.decode()

        # wines_by_type should contain the wine ID
        assert f'"id": {wine_id}' in html or f'"id":{wine_id}' in html

    def test_stats_tooltip_links_to_edit(self, client, sample_wine):
        """Tooltip items should use inline editWine() calls."""
        resp = client.get("/stats")
        html = resp.data.decode()
        # The JS template builds <a href="#" onclick="editWine(ID); return false;" class="chart-tooltip-item">
        assert "editWine(" in html
        assert "chart-tooltip-item" in html

    def test_stats_editwine_opens_view_modal(self, client, sample_wine):
        """Stats editWine() function should fetch wine data and open view modal in-place."""
        resp = client.get("/stats")
        html = resp.data.decode()
        assert "openViewModal" in html
        assert "/api/wine/" in html
        assert 'id="viewModal"' in html

    def test_stats_has_lightbox(self, client, sample_wine):
        """Stats page should contain the lightbox overlay for wine image viewing."""
        resp = client.get("/stats")
        html = resp.data.decode()
        assert 'id="lightbox"' in html
        assert "openLightbox" in html

    def test_stats_no_from_stats_links(self, client, sample_wine):
        """Stats page should not contain from=stats links (edit is inline now)."""
        resp = client.get("/stats")
        html = resp.data.decode()
        assert "from=stats" not in html

    def test_stats_has_edit_modal(self, client, sample_wine):
        """Stats page should contain the inline wine edit modal."""
        resp = client.get("/stats")
        html = resp.data.decode()
        assert 'id="wineModal"' in html
        assert 'id="wineForm"' in html


# ── GET /api/wine/<id> ────────────────────────────────────────────────────────

class TestApiGetWine:
    def test_get_existing_wine(self, client, sample_wine):
        wine_id = sample_wine["wine"]["id"]
        resp = client.get(f"/api/wine/{wine_id}")
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert data["wine"]["id"] == wine_id
        assert data["wine"]["name"] == "Château Test"

    def test_get_nonexistent_wine(self, client):
        resp = client.get("/api/wine/99999")
        assert resp.status_code == 404
        data = json.loads(resp.data)
        assert data["ok"] is False

    def test_get_wine_includes_all_fields(self, client):
        """API response should include all wine fields."""
        resp = client.post(
            "/add",
            data={
                "name": "Full Wine",
                "year": "2020",
                "type": "Rotwein",
                "quantity": "5",
                "region": "Toscana, IT",
                "grape": "Sangiovese",
                "price": "25.00",
                "bottle_format": "0.75",
            },
            headers=AJAX,
        )
        wine_id = json.loads(resp.data)["wine"]["id"]

        resp = client.get(f"/api/wine/{wine_id}")
        data = json.loads(resp.data)
        wine = data["wine"]
        assert wine["name"] == "Full Wine"
        assert wine["year"] == 2020
        assert wine["type"] == "Rotwein"
        assert wine["quantity"] == 5
        assert wine["region"] == "Toscana, IT"
        assert wine["grape"] == "Sangiovese"
        assert wine["price"] == 25.00
        assert wine["bottle_format"] == 0.75


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


# ── GET /chat ────────────────────────────────────────────────────────────────

class TestChatPage:
    """Tests for the /chat page route."""

    @patch("app.load_options")
    def test_chat_page_with_ai(self, mock_opts, client):
        mock_opts.return_value = {
            "currency": "CHF", "language": "en",
            "ai_provider": "anthropic", "anthropic_api_key": "sk-test",
            "anthropic_model": "claude-sonnet-4-20250514",
            "openai_api_key": "", "openrouter_api_key": "",
            "ollama_host": "", "ollama_model": "",
        }
        response = client.get("/chat")
        assert response.status_code == 200
        assert b"chatMessages" in response.data
        assert b"chatInput" in response.data

    @patch("app.load_options")
    def test_chat_page_without_ai_redirects(self, mock_opts, client):
        mock_opts.return_value = {
            "currency": "CHF", "language": "en",
            "ai_provider": "none", "anthropic_api_key": "",
            "openai_api_key": "", "openrouter_api_key": "",
            "ollama_host": "", "ollama_model": "",
        }
        response = client.get("/chat")
        assert response.status_code == 302

    @patch("app.load_options")
    def test_chat_wine_links_open_view_modal(self, mock_opts, client):
        """Chat page wine: link handler should open view modal in-place (not redirect)."""
        mock_opts.return_value = {
            "currency": "CHF", "language": "en",
            "ai_provider": "anthropic", "anthropic_api_key": "sk-test",
            "anthropic_model": "claude-sonnet-4-20250514",
            "openai_api_key": "", "openrouter_api_key": "",
            "ollama_host": "", "ollama_model": "",
        }
        response = client.get("/chat")
        html = response.data.decode()
        assert "openViewModal" in html
        assert "/api/wine/" in html
        assert 'id="viewModal"' in html


# ── Authentication ────────────────────────────────────────────────────────────

class TestAuth:
    """Tests for the optional authentication system (standalone Docker)."""

    def _make_auth_app(self, extra_users=None):
        """Create a test client with authentication enabled."""
        import app as wine_app

        wine_app.AUTH_ENABLED = True
        wine_app._USERS = {
            "admin": {"hash": generate_password_hash("secret", method="pbkdf2:sha256"), "role": "admin"},
            "user1": {"hash": generate_password_hash("pass123", method="pbkdf2:sha256"), "role": "admin"},
        }
        if extra_users:
            wine_app._USERS.update(extra_users)
        wine_app.app.config["TESTING"] = True
        wine_app.app.secret_key = "test-secret"
        wine_app.init_db()
        return wine_app.app.test_client()

    def teardown_method(self):
        """Reset auth state after each test."""
        import app as wine_app

        wine_app.AUTH_ENABLED = False
        wine_app._USERS = {}

    def test_no_auth_by_default(self, client):
        """With AUTH_ENABLED=false (default), all routes should be open."""
        resp = client.get("/")
        assert resp.status_code == 200

    def test_auth_redirects_to_login(self):
        """With AUTH_ENABLED=true, unauthenticated requests redirect to /login."""
        client = self._make_auth_app()
        resp = client.get("/")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_login_page_loads(self):
        """The /login page should render successfully."""
        client = self._make_auth_app()
        resp = client.get("/login")
        assert resp.status_code == 200
        assert b"Wine Tracker" in resp.data
        assert b"username" in resp.data

    def test_login_success(self):
        """Correct credentials should log the user in and redirect."""
        client = self._make_auth_app()
        resp = client.post(
            "/login",
            data={"username": "admin", "password": "secret"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/login" not in resp.headers.get("Location", "")

    def test_login_wrong_password(self):
        """Wrong password should re-render login page with error."""
        client = self._make_auth_app()
        resp = client.post(
            "/login",
            data={"username": "admin", "password": "wrong"},
        )
        assert resp.status_code == 200
        assert b"Invalid" in resp.data or b"error" in resp.data.lower()

    def test_login_unknown_user(self):
        """Unknown user should re-render login page."""
        client = self._make_auth_app()
        resp = client.post(
            "/login",
            data={"username": "nobody", "password": "test"},
        )
        assert resp.status_code == 200

    def test_logout(self):
        """Logout should clear the session and redirect to login."""
        client = self._make_auth_app()
        # Login first
        client.post("/login", data={"username": "admin", "password": "secret"})
        # Then logout
        resp = client.get("/logout")
        assert resp.status_code == 302
        # Verify logged out — next request should redirect to login
        resp = client.get("/")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_static_accessible_without_login(self):
        """Static files (CSS, JS) should be accessible without authentication."""
        client = self._make_auth_app()
        resp = client.get("/static/style.css")
        assert resp.status_code == 200

    def test_api_requires_auth(self):
        """API endpoints should return 401 when not authenticated."""
        client = self._make_auth_app()
        resp = client.get("/api/summary")
        assert resp.status_code == 401
        data = json.loads(resp.data)
        assert data["ok"] is False

    def test_authenticated_access(self):
        """After login, all routes should be accessible."""
        client = self._make_auth_app()
        client.post("/login", data={"username": "admin", "password": "secret"})
        resp = client.get("/")
        assert resp.status_code == 200

    def test_login_disabled_redirects_to_index(self, client):
        """/login should redirect to / when auth is disabled."""
        resp = client.get("/login")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/")

    # ── Readonly role tests ──────────────────────────────────────────────────

    def test_readonly_cannot_add(self):
        """Readonly users cannot add wines."""
        client = self._make_auth_app(extra_users={
            "viewer": {"hash": generate_password_hash("pass", method="pbkdf2:sha256"), "role": "readonly"},
        })
        client.post("/login", data={"username": "viewer", "password": "pass"})
        resp = client.post("/add", data={"name": "Test Wine"})
        assert resp.status_code in (302, 403)

    def test_readonly_cannot_delete(self):
        """Readonly users cannot delete wines."""
        client = self._make_auth_app(extra_users={
            "viewer": {"hash": generate_password_hash("pass", method="pbkdf2:sha256"), "role": "readonly"},
        })
        client.post("/login", data={"username": "viewer", "password": "pass"})
        resp = client.post("/delete/1")
        assert resp.status_code in (302, 403)

    def test_readonly_cannot_edit(self):
        """Readonly users cannot edit wines."""
        client = self._make_auth_app(extra_users={
            "viewer": {"hash": generate_password_hash("pass", method="pbkdf2:sha256"), "role": "readonly"},
        })
        client.post("/login", data={"username": "viewer", "password": "pass"})
        resp = client.post("/edit/1", data={"name": "Hacked"}, headers=AJAX)
        assert resp.status_code == 403
        data = json.loads(resp.data)
        assert data["error"] == "readonly"

    def test_readonly_cannot_duplicate(self):
        """Readonly users cannot duplicate wines."""
        client = self._make_auth_app(extra_users={
            "viewer": {"hash": generate_password_hash("pass", method="pbkdf2:sha256"), "role": "readonly"},
        })
        client.post("/login", data={"username": "viewer", "password": "pass"})
        resp = client.post("/duplicate/1", data={}, headers=AJAX)
        assert resp.status_code == 403

    def test_readonly_can_view(self):
        """Readonly users can view the wine list."""
        client = self._make_auth_app(extra_users={
            "viewer": {"hash": generate_password_hash("pass", method="pbkdf2:sha256"), "role": "readonly"},
        })
        client.post("/login", data={"username": "viewer", "password": "pass"})
        resp = client.get("/")
        assert resp.status_code == 200

    def test_readonly_can_view_stats(self):
        """Readonly users can view the stats page."""
        client = self._make_auth_app(extra_users={
            "viewer": {"hash": generate_password_hash("pass", method="pbkdf2:sha256"), "role": "readonly"},
        })
        client.post("/login", data={"username": "viewer", "password": "pass"})
        resp = client.get("/stats")
        assert resp.status_code == 200

    def test_readonly_can_chat(self):
        """Readonly users can use the chat API."""
        client = self._make_auth_app(extra_users={
            "viewer": {"hash": generate_password_hash("pass", method="pbkdf2:sha256"), "role": "readonly"},
        })
        client.post("/login", data={"username": "viewer", "password": "pass"})
        with patch("app.load_options") as mock_opts, patch("app._call_chat") as mock_chat:
            mock_opts.return_value = {
                "currency": "CHF", "language": "en",
                "ai_provider": "anthropic", "anthropic_api_key": "sk-test",
                "anthropic_model": "claude-sonnet-4-20250514",
                "openai_api_key": "", "openrouter_api_key": "",
                "ollama_host": "", "ollama_model": "",
            }
            mock_chat.return_value = "Nice wine!"
            resp = client.post(
                "/api/chat",
                data=json.dumps({"message": "hi", "history": []}),
                content_type="application/json",
            )
            assert resp.status_code == 200

    def test_readonly_hides_fab(self):
        """Readonly users should not see the FAB (add wine) button."""
        client = self._make_auth_app(extra_users={
            "viewer": {"hash": generate_password_hash("pass", method="pbkdf2:sha256"), "role": "readonly"},
        })
        client.post("/login", data={"username": "viewer", "password": "pass"})
        resp = client.get("/")
        assert b'class="fab"' not in resp.data

    def test_readonly_hides_card_actions(self):
        """Readonly users should not see card action buttons in server-rendered cards."""
        client = self._make_auth_app(extra_users={
            "viewer": {"hash": generate_password_hash("pass", method="pbkdf2:sha256"), "role": "readonly"},
        })
        # Login as admin first to add a wine
        client.post("/login", data={"username": "admin", "password": "secret"})
        client.post("/add", data={"name": "Visible Wine", "quantity": "2"}, headers=AJAX)
        client.get("/logout")
        # Login as readonly
        client.post("/login", data={"username": "viewer", "password": "pass"})
        resp = client.get("/")
        html = resp.data.decode()
        # The server-rendered card divs should not have card-actions
        # (the JS renderCard function string still exists in source but is
        # guarded by AUTH_READONLY, so we check the actual HTML cards only)
        # Count card-actions outside of <script> tags
        import re
        # Remove all script blocks from HTML
        html_no_script = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        assert 'class="card-actions"' not in html_no_script

    def test_admin_can_add(self):
        """Admin users can add wines normally."""
        client = self._make_auth_app()
        client.post("/login", data={"username": "admin", "password": "secret"})
        resp = client.post("/add", data={"name": "Admin Wine"}, headers=AJAX)
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True

    def test_readonly_blocks_api_write(self):
        """Readonly users cannot use write API endpoints."""
        client = self._make_auth_app(extra_users={
            "viewer": {"hash": generate_password_hash("pass", method="pbkdf2:sha256"), "role": "readonly"},
        })
        client.post("/login", data={"username": "viewer", "password": "pass"})
        resp = client.post(
            "/api/vivino-image",
            data=json.dumps({"url": "https://example.com/img.jpg"}),
            content_type="application/json",
        )
        assert resp.status_code == 403

    def test_login_sets_role_in_session(self):
        """Login should store the user role in the session."""
        client = self._make_auth_app(extra_users={
            "viewer": {"hash": generate_password_hash("pass", method="pbkdf2:sha256"), "role": "readonly"},
        })
        client.post("/login", data={"username": "viewer", "password": "pass"})
        # Verify by checking auth_readonly in template context
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"AUTH_READONLY = true" in resp.data
