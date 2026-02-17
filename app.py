import os
import sqlite3
import uuid
from datetime import date
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, g

app = Flask(__name__)

# Persist data in /share so it survives add-on restarts/updates
DATA_DIR = "/share/wine-tracker"
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "wine.db")

os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXT = {"jpg", "jpeg", "png", "webp", "gif"}
WINE_TYPES = ["Rotwein", "Weisswein", "Rosé", "Schaumwein", "Dessertwein", "Anderes"]


# ── Database ──────────────────────────────────────────────────────────────────

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS wines (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT    NOT NULL,
                year         INTEGER,
                type         TEXT,
                region       TEXT,
                quantity     INTEGER DEFAULT 1,
                rating       INTEGER DEFAULT 0,
                notes        TEXT,
                image        TEXT,
                added        TEXT,
                purchased_at TEXT,
                price        REAL,
                drink_from   INTEGER,
                drink_until  INTEGER,
                location     TEXT
            )
        """)
        # Migrate existing DBs – add columns if missing
        existing = {row[1] for row in db.execute("PRAGMA table_info(wines)")}
        migrations = {
            "purchased_at": "TEXT",
            "price":        "REAL",
            "drink_from":   "INTEGER",
            "drink_until":  "INTEGER",
            "location":     "TEXT",
        }
        for col, dtype in migrations.items():
            if col not in existing:
                db.execute(f"ALTER TABLE wines ADD COLUMN {col} {dtype}")
        db.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

def allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def save_image(file):
    if file and file.filename and allowed(file.filename):
        ext = file.filename.rsplit(".", 1)[1].lower()
        fname = f"{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(UPLOAD_DIR, fname))
        return fname
    return None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    db = get_db()
    q = request.args.get("q", "").strip()
    t = request.args.get("type", "")
    show_empty = request.args.get("show_empty", "1")

    sql = "SELECT * FROM wines WHERE 1=1"
    params = []

    if q:
        sql += " AND (name LIKE ? OR region LIKE ? OR notes LIKE ?)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    if t:
        sql += " AND type = ?"
        params.append(t)
    if show_empty == "0":
        sql += " AND quantity > 0"

    sql += " ORDER BY type, name, year"
    wines = db.execute(sql, params).fetchall()

    stats = db.execute(
        "SELECT COUNT(*) as cnt, SUM(quantity) as total FROM wines WHERE quantity > 0"
    ).fetchone()

    return render_template(
        "index.html",
        wines=wines,
        wine_types=WINE_TYPES,
        query=q,
        active_type=t,
        show_empty=show_empty,
        stats=stats,
    )


@app.route("/add", methods=["POST"])
def add():
    db = get_db()
    image = save_image(request.files.get("image"))
    price_raw = request.form.get("price", "").strip()
    db.execute(
        """INSERT INTO wines
           (name, year, type, region, quantity, rating, notes, image, added,
            purchased_at, price, drink_from, drink_until, location)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            request.form["name"].strip(),
            request.form.get("year") or None,
            request.form.get("type"),
            request.form.get("region", "").strip(),
            int(request.form.get("quantity", 1)),
            int(request.form.get("rating", 0)),
            request.form.get("notes", "").strip(),
            image,
            str(date.today()),
            request.form.get("purchased_at", "").strip() or None,
            float(price_raw) if price_raw else None,
            request.form.get("drink_from") or None,
            request.form.get("drink_until") or None,
            request.form.get("location", "").strip() or None,
        ),
    )
    db.commit()
    return redirect(url_for("index"))


@app.route("/edit/<int:wine_id>", methods=["POST"])
def edit(wine_id):
    db = get_db()
    wine = db.execute("SELECT * FROM wines WHERE id=?", (wine_id,)).fetchone()
    if not wine:
        return redirect(url_for("index"))

    image = wine["image"]
    new_image = save_image(request.files.get("image"))
    if new_image:
        # Remove old image
        if image:
            try:
                os.remove(os.path.join(UPLOAD_DIR, image))
            except FileNotFoundError:
                pass
        image = new_image

    price_raw = request.form.get("price", "").strip()
    db.execute(
        """UPDATE wines SET name=?, year=?, type=?, region=?, quantity=?, rating=?,
           notes=?, image=?, purchased_at=?, price=?, drink_from=?, drink_until=?, location=?
           WHERE id=?""",
        (
            request.form["name"].strip(),
            request.form.get("year") or None,
            request.form.get("type"),
            request.form.get("region", "").strip(),
            int(request.form.get("quantity", 0)),
            int(request.form.get("rating", 0)),
            request.form.get("notes", "").strip(),
            image,
            request.form.get("purchased_at", "").strip() or None,
            float(price_raw) if price_raw else None,
            request.form.get("drink_from") or None,
            request.form.get("drink_until") or None,
            request.form.get("location", "").strip() or None,
            wine_id,
        ),
    )
    db.commit()
    return redirect(url_for("index"))


@app.route("/duplicate/<int:wine_id>", methods=["POST"])
def duplicate(wine_id):
    db = get_db()
    wine = db.execute("SELECT * FROM wines WHERE id=?", (wine_id,)).fetchone()
    if not wine:
        return redirect(url_for("index"))

    new_year = request.form.get("new_year") or wine["year"]

    db.execute(
        "INSERT INTO wines (name, year, type, region, quantity, rating, notes, image, added) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            wine["name"],
            new_year,
            wine["type"],
            wine["region"],
            int(request.form.get("quantity", wine["quantity"])),
            wine["rating"],
            wine["notes"],
            wine["image"],  # share same image
            str(date.today()),
        ),
    )
    db.commit()
    return redirect(url_for("index"))


@app.route("/delete/<int:wine_id>", methods=["POST"])
def delete(wine_id):
    db = get_db()
    wine = db.execute("SELECT image FROM wines WHERE id=?", (wine_id,)).fetchone()
    if wine and wine["image"]:
        # Only delete image if no other wine uses it
        count = db.execute(
            "SELECT COUNT(*) FROM wines WHERE image=? AND id!=?", (wine["image"], wine_id)
        ).fetchone()[0]
        if count == 0:
            try:
                os.remove(os.path.join(UPLOAD_DIR, wine["image"]))
            except FileNotFoundError:
                pass
    db.execute("DELETE FROM wines WHERE id=?", (wine_id,))
    db.commit()
    return redirect(url_for("index"))


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


# ── API for Home Assistant sensors ───────────────────────────────────────────

@app.route("/api/summary")
def api_summary():
    db = get_db()
    rows = db.execute(
        "SELECT type, COUNT(*) as cnt, SUM(quantity) as total FROM wines GROUP BY type"
    ).fetchall()
    total = db.execute("SELECT SUM(quantity) FROM wines WHERE quantity > 0").fetchone()[0] or 0
    return jsonify({"total_bottles": total, "by_type": [dict(r) for r in rows]})


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5050, debug=False)
