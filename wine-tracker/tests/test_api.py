"""
Tests for AI and Vivino API endpoints.
External services are mocked to avoid real API calls.
"""
import html
import io
import json
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

APP_DIR = os.path.join(os.path.dirname(__file__), "..", "app")
sys.path.insert(0, APP_DIR)

import app as wine_app

AJAX = {"X-Requested-With": "XMLHttpRequest"}


# ── POST /api/analyze-wine (AI label recognition) ────────────────────────────

class TestAnalyzeWine:
    def test_no_ai_configured(self, client):
        """Should return error if no AI provider configured."""
        fake_image = (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100), "label.png")
        resp = client.post(
            "/api/analyze-wine",
            data={"image": fake_image},
            content_type="multipart/form-data",
        )
        data = json.loads(resp.data)
        assert data.get("ok") is False
        assert data.get("error") == "no_api_key"
        assert resp.status_code == 400

    @patch("app.load_options")
    def test_no_image_provided(self, mock_opts, client):
        """Should return error if no image is uploaded."""
        mock_opts.return_value = {
            **wine_app.HA_OPTIONS,
            "ai_provider": "anthropic",
            "anthropic_api_key": "sk-test",
        }
        resp = client.post("/api/analyze-wine", data={}, content_type="multipart/form-data")
        data = json.loads(resp.data)
        assert data.get("ok") is False
        assert resp.status_code == 400

    @patch("app._call_anthropic")
    @patch("app.load_options")
    def test_anthropic_success(self, mock_opts, mock_call, client):
        """Should return parsed wine fields from AI response."""
        mock_opts.return_value = {
            **wine_app.HA_OPTIONS,
            "ai_provider": "anthropic",
            "anthropic_api_key": "sk-test",
        }
        mock_call.return_value = json.dumps({
            "name": "Château Margaux",
            "wine_type": "Rotwein",
            "vintage": 2015,
            "region": "Bordeaux, FR",
            "grape": "Cabernet Sauvignon",
            "price": None,
            "notes": "Full-bodied",
            "drink_from": 2020,
            "drink_until": 2040,
            "bottle_format": 0.75,
        })

        fake_image = (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100), "label.png")
        resp = client.post(
            "/api/analyze-wine",
            data={"image": fake_image},
            content_type="multipart/form-data",
        )
        data = json.loads(resp.data)
        assert resp.status_code == 200
        assert data["ok"] is True
        assert "fields" in data
        assert data["fields"]["name"] == "Château Margaux"
        assert data["fields"]["wine_type"] == "Rotwein"
        assert "image_filename" in data

    @patch("app._call_openai")
    @patch("app.load_options")
    def test_openai_provider(self, mock_opts, mock_call, client):
        """Should use OpenAI when configured."""
        mock_opts.return_value = {
            **wine_app.HA_OPTIONS,
            "ai_provider": "openai",
            "openai_api_key": "sk-test",
        }
        mock_call.return_value = json.dumps({
            "name": "Test Wine",
            "wine_type": "Weisswein",
            "vintage": 2020,
            "region": "Napa Valley",
            "grape": "Chardonnay",
            "price": None,
            "notes": "",
            "drink_from": None,
            "drink_until": None,
            "bottle_format": None,
        })

        fake_image = (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100), "test.jpg")
        resp = client.post(
            "/api/analyze-wine",
            data={"image": fake_image},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert data["fields"]["name"] == "Test Wine"

    @patch("app._call_anthropic")
    @patch("app.load_options")
    def test_ai_json_parse_error(self, mock_opts, mock_call, client):
        """Should return parse_error if AI returns invalid JSON."""
        mock_opts.return_value = {
            **wine_app.HA_OPTIONS,
            "ai_provider": "anthropic",
            "anthropic_api_key": "sk-test",
        }
        mock_call.return_value = "This is not valid JSON at all"

        fake_image = (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100), "label.png")
        resp = client.post(
            "/api/analyze-wine",
            data={"image": fake_image},
            content_type="multipart/form-data",
        )
        data = json.loads(resp.data)
        assert resp.status_code == 500
        assert data["ok"] is False
        assert data["error"] == "parse_error"


# ── POST /api/reanalyze-wine ─────────────────────────────────────────────────

class TestReanalyzeWine:
    def test_no_ai_configured(self, client):
        resp = client.post(
            "/api/reanalyze-wine",
            data=json.dumps({"image_filename": "test.jpg", "wine_context": {}}),
            content_type="application/json",
        )
        data = json.loads(resp.data)
        assert data.get("ok") is False or resp.status_code >= 400


# ── GET /api/vivino-search ────────────────────────────────────────────────────

class TestVivinoSearch:
    def test_empty_query(self, client):
        resp = client.get("/api/vivino-search?q=")
        data = json.loads(resp.data)
        assert data.get("ok") is False or resp.status_code >= 400

    def test_short_query(self, client):
        resp = client.get("/api/vivino-search?q=a")
        data = json.loads(resp.data)
        assert resp.status_code == 400
        assert data.get("error") == "query_too_short"

    @patch("requests.get")
    def test_vivino_search_success(self, mock_get, client):
        """Should parse Vivino search results from data-preloaded-state."""
        # Build the JSON that Vivino embeds in data-preloaded-state
        preloaded = {
            "search_results": {
                "matches": [
                    {
                        "vintage": {
                            "year": 2020,
                            "wine": {
                                "id": 12345,
                                "name": "Reserve",
                                "type_id": 1,
                                "winery": {"name": "TestWinery"},
                                "region": {
                                    "name": "Bordeaux",
                                    "country": {"name": "France"},
                                },
                                "grapes": [
                                    {"grape": {"name": "Merlot"}}
                                ],
                            },
                            "statistics": {"wine_ratings_average": 4.2},
                            "image": {"location": "//images.vivino.com/test.png"},
                        },
                        "price": {"amount": 29.99},
                    }
                ]
            }
        }
        escaped = html.escape(json.dumps(preloaded))
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = f'<div id="search-page" data-preloaded-state="{escaped}"></div>'
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        resp = client.get("/api/vivino-search?q=TestWinery+Reserve")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert len(data["results"]) == 1
        assert data["results"][0]["name"] == "TestWinery Reserve"

    @patch("requests.get")
    def test_vivino_search_no_results(self, mock_get, client):
        """Should return empty results when no matches."""
        preloaded = {"search_results": {"matches": []}}
        escaped = html.escape(json.dumps(preloaded))
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = f'<div data-preloaded-state="{escaped}"></div>'
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        resp = client.get("/api/vivino-search?q=NonexistentWine12345")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert data["results"] == []


# ── POST /api/vivino-image ────────────────────────────────────────────────────

class TestVivinoImage:
    @patch("app._downscale")
    @patch("requests.get")
    def test_download_vivino_image(self, mock_get, mock_downscale, client, upload_dir):
        """Should download and save image from URL."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        mock_response.headers = {"Content-Type": "image/png"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        resp = client.post(
            "/api/vivino-image",
            data=json.dumps({"url": "https://images.vivino.com/test.png"}),
            content_type="application/json",
        )
        data = json.loads(resp.data)
        assert resp.status_code == 200
        assert data["ok"] is True
        assert "filename" in data
        assert os.path.isfile(os.path.join(upload_dir, data["filename"]))

    def test_no_url_provided(self, client):
        """Should return error if no URL is provided."""
        resp = client.post(
            "/api/vivino-image",
            data=json.dumps({"url": ""}),
            content_type="application/json",
        )
        data = json.loads(resp.data)
        assert resp.status_code == 400
        assert data.get("ok") is False


# ── GET /uploads/<filename> ───────────────────────────────────────────────────

class TestUploadServing:
    def test_serve_uploaded_file(self, client, upload_dir):
        """Should serve files from the uploads directory."""
        # Create a dummy file
        test_file = os.path.join(upload_dir, "test_image.png")
        with open(test_file, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        resp = client.get("/uploads/test_image.png")
        assert resp.status_code == 200

    def test_serve_nonexistent_file(self, client):
        resp = client.get("/uploads/nonexistent.png")
        assert resp.status_code == 404
