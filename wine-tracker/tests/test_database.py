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


class TestWineLogTable:
    def test_timeline_table_created(self, app):
        """init_db() should create the timeline table."""
        conn = sqlite3.connect(wine_app.DB_PATH)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='timeline'"
        ).fetchone()
        conn.close()
        assert tables is not None

    def test_timeline_has_all_columns(self, app):
        """timeline table should have all expected columns."""
        conn = sqlite3.connect(wine_app.DB_PATH)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(timeline)")}
        conn.close()
        expected = {"id", "wine_id", "action", "quantity", "timestamp"}
        assert expected.issubset(cols)

    def test_backfill_existing_wines(self, app, db):
        """Existing wines should be backfilled into timeline on first init."""
        # Insert a wine directly (simulating pre-existing data)
        db.execute(
            "INSERT INTO wines (name, quantity, added) VALUES (?, ?, ?)",
            ("Backfill Wine", 5, "2025-01-15"),
        )
        db.commit()

        # Clear the log and re-run init to trigger backfill
        db.execute("DELETE FROM timeline")
        db.commit()
        wine_app.init_db()

        conn = sqlite3.connect(wine_app.DB_PATH)
        conn.row_factory = sqlite3.Row
        logs = conn.execute("SELECT * FROM timeline WHERE action='added'").fetchall()
        conn.close()
        assert len(logs) >= 1
        # Find the backfill entry for our wine
        backfill = [l for l in logs if l["quantity"] == 5]
        assert len(backfill) >= 1
        assert backfill[0]["timestamp"] == "2025-01-15"

    def test_backfill_only_when_empty(self, app, db):
        """Backfill should only happen when timeline is empty."""
        # Add a wine via the app (creates a log entry)
        db.execute(
            "INSERT INTO wines (name, quantity, added) VALUES (?, ?, ?)",
            ("Existing Wine", 2, "2025-06-01"),
        )
        db.execute(
            "INSERT INTO timeline (wine_id, action, quantity, timestamp) VALUES (?, ?, ?, ?)",
            (1, "added", 2, "2025-06-01"),
        )
        db.commit()

        # Re-run init_db — should NOT duplicate entries
        wine_app.init_db()

        conn = sqlite3.connect(wine_app.DB_PATH)
        count = conn.execute("SELECT COUNT(*) FROM timeline").fetchone()[0]
        conn.close()
        assert count == 1  # No duplicates


class TestChatSessionTables:
    def test_chat_sessions_table_created(self, app):
        """init_db() should create the chat_sessions table."""
        conn = sqlite3.connect(wine_app.DB_PATH)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chat_sessions'"
        ).fetchone()
        conn.close()
        assert tables is not None

    def test_chat_messages_table_created(self, app):
        """init_db() should create the chat_messages table."""
        conn = sqlite3.connect(wine_app.DB_PATH)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chat_messages'"
        ).fetchone()
        conn.close()
        assert tables is not None

    def test_chat_sessions_has_all_columns(self, app):
        """chat_sessions table should have all expected columns."""
        conn = sqlite3.connect(wine_app.DB_PATH)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(chat_sessions)")}
        conn.close()
        expected = {"id", "title", "created", "updated"}
        assert expected.issubset(cols)

    def test_chat_messages_has_all_columns(self, app):
        """chat_messages table should have all expected columns."""
        conn = sqlite3.connect(wine_app.DB_PATH)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(chat_messages)")}
        conn.close()
        expected = {"id", "session_id", "role", "content", "timestamp", "image_path"}
        assert expected.issubset(cols)

    def test_cascade_delete(self, app, db):
        """Deleting a chat session should CASCADE delete its messages."""
        db.execute("PRAGMA foreign_keys = ON")
        db.execute(
            "INSERT INTO chat_sessions (id, title, created, updated) VALUES (?, ?, ?, ?)",
            (1, "Test Session", "2025-01-01", "2025-01-01"),
        )
        db.execute(
            "INSERT INTO chat_messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (1, "user", "Hello", "2025-01-01"),
        )
        db.execute(
            "INSERT INTO chat_messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (1, "assistant", "Hi there!", "2025-01-01"),
        )
        db.commit()

        # Verify messages exist
        count = db.execute("SELECT COUNT(*) FROM chat_messages WHERE session_id = 1").fetchone()[0]
        assert count == 2

        # Delete session
        db.execute("DELETE FROM chat_sessions WHERE id = 1")
        db.commit()

        # Messages should be gone
        count = db.execute("SELECT COUNT(*) FROM chat_messages WHERE session_id = 1").fetchone()[0]
        assert count == 0


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


class TestMaturityTasteFoodColumns:
    """Tests for maturity_data, taste_profile, food_pairings columns."""

    def test_migration_adds_new_columns(self, app):
        """init_db() should add maturity_data, taste_profile, food_pairings columns."""
        conn = sqlite3.connect(wine_app.DB_PATH)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(wines)")}
        conn.close()
        assert "maturity_data" in cols
        assert "taste_profile" in cols
        assert "food_pairings" in cols

    def test_migration_from_old_schema_adds_new_columns(self):
        """Migrating from a schema without maturity/taste/food should add them."""
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

        wine_app.init_db()

        conn = sqlite3.connect(wine_app.DB_PATH)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(wines)")}
        conn.close()

        for col in ["maturity_data", "taste_profile", "food_pairings"]:
            assert col in cols, f"Migration did not add column: {col}"

    def test_new_columns_default_null(self, app, db):
        """New columns should default to NULL."""
        db.execute(
            "INSERT INTO wines (name, quantity) VALUES (?, ?)",
            ("Test Wine", 1)
        )
        db.commit()
        row = db.execute(
            "SELECT maturity_data, taste_profile, food_pairings FROM wines WHERE name='Test Wine'"
        ).fetchone()
        assert row["maturity_data"] is None
        assert row["taste_profile"] is None
        assert row["food_pairings"] is None

    def test_store_and_retrieve_json_data(self, app, db):
        """JSON data should be stored and retrievable from new columns."""
        import json
        maturity = json.dumps({"youth": [2020, 2024], "maturity": [2025, 2031],
                               "peak": [2032, 2044], "decline": [2045, 2054]})
        taste = json.dumps({"body": 4, "tannin": 5, "acidity": 3, "sweetness": 1})
        food = json.dumps(["Lamb", "Beef stew", "Hard cheese"])

        db.execute(
            "INSERT INTO wines (name, quantity, maturity_data, taste_profile, food_pairings) VALUES (?,?,?,?,?)",
            ("JSON Wine", 1, maturity, taste, food)
        )
        db.commit()
        row = db.execute(
            "SELECT maturity_data, taste_profile, food_pairings FROM wines WHERE name='JSON Wine'"
        ).fetchone()
        assert json.loads(row["maturity_data"])["peak"] == [2032, 2044]
        assert json.loads(row["taste_profile"])["body"] == 4
        assert "Lamb" in json.loads(row["food_pairings"])


class TestFilterPresetsTable:
    """Tests for filter_presets table (advanced filter)."""

    def test_filter_presets_table_created(self, app):
        conn = sqlite3.connect(wine_app.DB_PATH)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='filter_presets'"
        ).fetchone()
        conn.close()
        assert tables is not None

    def test_filter_presets_has_all_columns(self, app):
        conn = sqlite3.connect(wine_app.DB_PATH)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(filter_presets)")}
        conn.close()
        expected = {"id", "name", "conditions", "created", "updated"}
        assert expected.issubset(cols)

    def test_name_is_unique(self, app, db):
        db.execute(
            "INSERT INTO filter_presets (name, conditions, created, updated) VALUES (?, ?, ?, ?)",
            ("My Preset", "{}", "2026-04-22", "2026-04-22"),
        )
        db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO filter_presets (name, conditions, created, updated) VALUES (?, ?, ?, ?)",
                ("My Preset", "{}", "2026-04-22", "2026-04-22"),
            )
            db.commit()

    def test_init_db_is_idempotent(self, app):
        """Running init_db() twice should not fail."""
        wine_app.init_db()
        conn = sqlite3.connect(wine_app.DB_PATH)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='filter_presets'"
        ).fetchone()
        conn.close()
        assert tables is not None
