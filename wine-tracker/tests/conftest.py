"""
Shared pytest fixtures for Wine Tracker tests.

Provides a Flask test client with an in-memory SQLite database,
isolated from production data.
"""
import json
import os
import sys
import tempfile
import shutil

import pytest

# ── Make app module importable ────────────────────────────────────────────────
APP_DIR = os.path.join(os.path.dirname(__file__), "..", "app")
sys.path.insert(0, APP_DIR)


@pytest.fixture(autouse=True)
def _patch_env(tmp_path, monkeypatch):
    """
    Patch all global state in app.py so each test gets:
    - A fresh temporary directory for DATA_DIR / UPLOAD_DIR / DB_PATH
    - Default HA options (no AI, CHF, German)
    """
    data_dir = str(tmp_path / "data")
    upload_dir = os.path.join(data_dir, "uploads")
    db_path = os.path.join(data_dir, "wine.db")
    os.makedirs(upload_dir, exist_ok=True)

    import app as wine_app

    monkeypatch.setattr(wine_app, "DATA_DIR", data_dir)
    monkeypatch.setattr(wine_app, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(wine_app, "DB_PATH", db_path)

    # Sensible default options for tests
    test_options = {
        "currency": "CHF",
        "language": "de",
        "ai_provider": "none",
        "anthropic_api_key": "",
        "anthropic_model": "claude-opus-4-6",
        "openai_api_key": "",
        "openai_model": "gpt-4o",
        "openrouter_api_key": "",
        "openrouter_model": "anthropic/claude-opus-4.6",
        "ollama_host": "http://localhost:11434",
        "ollama_model": "llava",
    }
    monkeypatch.setattr(wine_app, "HA_OPTIONS", test_options)


@pytest.fixture
def app():
    """Create a Flask test app with a fresh database."""
    import app as wine_app

    wine_app.app.config["TESTING"] = True
    wine_app.init_db()

    yield wine_app.app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def db(app):
    """Direct database connection for assertions."""
    import sqlite3
    import app as wine_app

    conn = sqlite3.connect(wine_app.DB_PATH)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def sample_wine(client):
    """Insert a sample wine and return its data."""
    resp = client.post(
        "/add",
        data={
            "name": "Château Test",
            "year": "2020",
            "type": "Rotwein",
            "region": "Bordeaux, FR",
            "quantity": "3",
            "rating": "4",
            "notes": "Excellent test wine",
            "purchased_at": "Testshop",
            "price": "29.90",
            "drink_from": "2023",
            "drink_until": "2030",
            "location": "Keller A",
            "grape": "Merlot",
            "bottle_format": "0.75",
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    return json.loads(resp.data)


@pytest.fixture
def upload_dir():
    """Return the current test UPLOAD_DIR path."""
    import app as wine_app
    return wine_app.UPLOAD_DIR
