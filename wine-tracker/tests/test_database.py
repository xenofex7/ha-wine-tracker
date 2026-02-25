"""
Tests for database initialization, migrations, and data operations.
"""
import os
import sys
import sqlite3

import pytest

APP_DIR = os.path.join(os.path.dirname(__file__), "..", "app")
sys.path.insert(0, APP_DIR)

import app as wine_app


class TestInitDb:
    def test_creates_wines_table(self, app):
        """init_db() should create the wines table."""
        conn = sqlite3.connect(wine_app.DB_PATH)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='wines'"
        ).fetchone()
        conn.close()
        assert tables is not None

    def test_table_has_all_columns(self, app):
        """wines table should have all expected columns."""
        conn = sqlite3.connect(wine_app.DB_PATH)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(wines)")}
        conn.close()

        expected = {
            "id", "name", "year", "type", "region", "quantity", "rating",
            "notes", "image", "added", "purchased_at", "price",
            "drink_from", "drink_until", "location", "grape",
            "vivino_id", "bottle_format",
        }
        assert expected.issubset(cols)

    def test_migration_adds_missing_columns(self, app):
        """Running init_db() again should not fail (idempotent)."""
        wine_app.init_db()  # second call
        conn = sqlite3.connect(wine_app.DB_PATH)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(wines)")}
        conn.close()
        assert "bottle_format" in cols
        assert "vivino_id" in cols

    def test_migration_from_old_schema(self):
        """
        Simulates an old DB without newer columns.
        init_db() should add them via migration.
        """
        conn = sqlite3.connect(wine_app.DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS wines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                year INTEGER,
                type TEXT,
                region TEXT,
                quantity INTEGER DEFAULT 1,
                rating INTEGER DEFAULT 0,
                notes TEXT,
                image TEXT,
                added TEXT
            )
        """)
        conn.commit()
        conn.close()

        # Now run init_db() – should add missing columns
        wine_app.init_db()

        conn = sqlite3.connect(wine_app.DB_PATH)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(wines)")}
        conn.close()

        for col in ["purchased_at", "price", "drink_from", "drink_until",
                     "location", "grape", "vivino_id", "bottle_format"]:
            assert col in cols, f"Migration did not add column: {col}"

    def test_bottle_format_default_value(self, app, db):
        """Inserted wines without bottle_format should default to 0.75."""
        db.execute(
            "INSERT INTO wines (name, quantity) VALUES (?, ?)",
            ("Default Bottle", 1)
        )
        db.commit()
        row = db.execute("SELECT bottle_format FROM wines WHERE name='Default Bottle'").fetchone()
        assert row["bottle_format"] == 0.75


class TestDatabaseOperations:
    def test_insert_and_read(self, app, db):
        """Basic insert and read."""
        db.execute(
            "INSERT INTO wines (name, year, type, region, quantity) VALUES (?,?,?,?,?)",
            ("Testvin", 2020, "Rotwein", "Tessin", 2),
        )
        db.commit()
        row = db.execute("SELECT * FROM wines WHERE name='Testvin'").fetchone()
        assert row is not None
        assert row["year"] == 2020
        assert row["type"] == "Rotwein"
        assert row["quantity"] == 2

    def test_wine_json_helper(self, client, sample_wine):
        """wine_json() should return a dict with all fields."""
        wine = sample_wine["wine"]
        assert wine["name"] == "Château Test"
        assert wine["year"] == 2020
        assert wine["type"] == "Rotwein"
        assert wine["region"] == "Bordeaux, FR"
        assert wine["quantity"] == 3
        assert wine["rating"] == 4
        assert wine["grape"] == "Merlot"
        assert wine["bottle_format"] == 0.75

    def test_stats_json_helper(self, client, sample_wine):
        """stats_json() should return correct totals."""
        stats = sample_wine["stats"]
        assert stats["total"] == 3
        assert stats["types"] == 1
