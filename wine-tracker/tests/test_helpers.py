"""
Unit tests for pure helper functions in app.py.
These tests don't need Flask request context (where possible).
"""
import os
import sys

import pytest

APP_DIR = os.path.join(os.path.dirname(__file__), "..", "app")
sys.path.insert(0, APP_DIR)

import app as wine_app


# ── load_options() ────────────────────────────────────────────────────────────

class TestLoadOptions:
    def test_defaults_when_file_missing(self, monkeypatch):
        monkeypatch.setattr(wine_app, "OPTIONS_PATH", "/nonexistent/options.json")
        opts = wine_app.load_options()
        assert opts["currency"] == "CHF"
        assert opts["language"] == "de"
        assert opts["ai_provider"] == "none"

    def test_loads_from_json(self, tmp_path, monkeypatch):
        opts_file = tmp_path / "options.json"
        opts_file.write_text('{"currency": "EUR", "language": "en"}')
        monkeypatch.setattr(wine_app, "OPTIONS_PATH", str(opts_file))
        opts = wine_app.load_options()
        assert opts["currency"] == "EUR"
        assert opts["language"] == "en"
        # Defaults still present for unset keys
        assert opts["ai_provider"] == "none"

    def test_backward_compat_anthropic_autodetect(self, tmp_path, monkeypatch):
        opts_file = tmp_path / "options.json"
        opts_file.write_text('{"anthropic_api_key": "sk-test-123"}')
        monkeypatch.setattr(wine_app, "OPTIONS_PATH", str(opts_file))
        opts = wine_app.load_options()
        assert opts["ai_provider"] == "anthropic"

    def test_invalid_json_uses_defaults(self, tmp_path, monkeypatch):
        opts_file = tmp_path / "options.json"
        opts_file.write_text("{broken json")
        monkeypatch.setattr(wine_app, "OPTIONS_PATH", str(opts_file))
        opts = wine_app.load_options()
        assert opts["currency"] == "CHF"


# ── _is_ai_configured() ──────────────────────────────────────────────────────

class TestIsAiConfigured:
    def test_none_provider(self):
        assert wine_app._is_ai_configured({"ai_provider": "none"}) is False

    def test_anthropic_with_key(self):
        assert wine_app._is_ai_configured(
            {"ai_provider": "anthropic", "anthropic_api_key": "sk-123"}
        ) is True

    def test_anthropic_without_key(self):
        assert wine_app._is_ai_configured(
            {"ai_provider": "anthropic", "anthropic_api_key": ""}
        ) is False

    def test_openai_with_key(self):
        assert wine_app._is_ai_configured(
            {"ai_provider": "openai", "openai_api_key": "sk-456"}
        ) is True

    def test_openrouter_with_key(self):
        assert wine_app._is_ai_configured(
            {"ai_provider": "openrouter", "openrouter_api_key": "or-789"}
        ) is True

    def test_ollama_with_host(self):
        assert wine_app._is_ai_configured(
            {"ai_provider": "ollama", "ollama_host": "http://localhost:11434"}
        ) is True

    def test_ollama_empty_host(self):
        assert wine_app._is_ai_configured(
            {"ai_provider": "ollama", "ollama_host": ""}
        ) is False

    def test_unknown_provider(self):
        assert wine_app._is_ai_configured({"ai_provider": "unknown"}) is False

    def test_whitespace_in_key(self):
        assert wine_app._is_ai_configured(
            {"ai_provider": "anthropic", "anthropic_api_key": "   "}
        ) is False


# ── allowed() ─────────────────────────────────────────────────────────────────

class TestAllowed:
    @pytest.mark.parametrize("filename,expected", [
        ("photo.jpg", True),
        ("photo.jpeg", True),
        ("photo.png", True),
        ("photo.webp", True),
        ("photo.gif", True),
        ("photo.JPG", True),      # case-insensitive
        ("photo.bmp", False),
        ("photo.svg", False),
        ("photo", False),          # no extension
        (".jpg", True),            # edge case: dot + ext
        ("photo.txt", False),
        ("photo.pdf", False),
    ])
    def test_allowed_extensions(self, filename, expected):
        assert wine_app.allowed(filename) == expected


# ── geocode_region() ──────────────────────────────────────────────────────────

class TestGeocodeRegion:
    def test_none_input(self):
        assert wine_app.geocode_region(None) is None

    def test_empty_string(self):
        assert wine_app.geocode_region("") is None

    def test_exact_match(self):
        coords = wine_app.geocode_region("Bordeaux")
        assert coords is not None
        assert isinstance(coords, list)
        assert len(coords) == 2

    def test_case_insensitive(self):
        c1 = wine_app.geocode_region("bordeaux")
        c2 = wine_app.geocode_region("BORDEAUX")
        c3 = wine_app.geocode_region("Bordeaux")
        assert c1 == c2 == c3

    def test_country_match(self):
        assert wine_app.geocode_region("Frankreich") is not None
        assert wine_app.geocode_region("France") is not None

    def test_substring_match(self):
        # "Toskana, Italien" should find "toskana"
        coords = wine_app.geocode_region("Toskana, Italien")
        assert coords is not None

    def test_unknown_region(self):
        assert wine_app.geocode_region("Planet Mars") is None


# ── format_date_filter() ──────────────────────────────────────────────────────

class TestFormatDate:
    def test_empty_value(self, app):
        with app.app_context():
            assert wine_app.format_date_filter("") == ""
            assert wine_app.format_date_filter(None) == ""

    def test_valid_date_german(self, app, monkeypatch):
        monkeypatch.setattr(wine_app, "LANG", "de")
        with app.app_context():
            result = wine_app.format_date_filter("2024-03-15")
            assert result == "15.03.2024"

    def test_valid_date_english(self, app, monkeypatch):
        monkeypatch.setattr(wine_app, "LANG", "en")
        with app.app_context():
            result = wine_app.format_date_filter("2024-03-15")
            assert result == "03/15/2024"

    def test_invalid_date(self, app):
        with app.app_context():
            assert wine_app.format_date_filter("not-a-date") == "not-a-date"


# ── translate_wine_type() ─────────────────────────────────────────────────────

class TestTranslateWineType:
    def test_known_type(self, app, monkeypatch):
        from translations import TRANSLATIONS
        monkeypatch.setattr(wine_app, "T", TRANSLATIONS["en"])
        with app.app_context():
            result = wine_app.translate_wine_type("Rotwein")
            assert result == "Red Wine"

    def test_unknown_type_passthrough(self, app):
        with app.app_context():
            assert wine_app.translate_wine_type("UnknownType") == "UnknownType"


# ── _vivino_country_code() ────────────────────────────────────────────────────

class TestVivinoCountryCode:
    def test_known_currencies(self):
        assert wine_app._vivino_country_code("EUR") == ("DE", "EUR")
        assert wine_app._vivino_country_code("USD") == ("US", "USD")
        assert wine_app._vivino_country_code("GBP") == ("GB", "GBP")
        assert wine_app._vivino_country_code("CHF") == ("CH", "CHF")

    def test_unknown_currency_default(self):
        assert wine_app._vivino_country_code("JPY") == ("US", "USD")


# ── _wine_json_schema() / _wine_json_rules() ─────────────────────────────────

class TestWineJsonSchema:
    def test_schema_contains_all_fields(self):
        schema = wine_app._wine_json_schema()
        for field in ["name", "year", "type", "region", "grape", "price", "notes", "bottle_format"]:
            assert field in schema

    def test_rules_contain_bottle_format(self):
        rules = wine_app._wine_json_rules("de")
        assert "bottle_format" in rules
        assert "0.75" in rules
