import json
import os
import shutil
import sqlite3
import uuid
from datetime import date
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, g
from translations import TRANSLATIONS

app = Flask(__name__)

# ── HA Add-on Options ─────────────────────────────────────────────────────────
OPTIONS_PATH = "/data/options.json"

def load_options():
    """Read HA add-on options with sensible defaults."""
    defaults = {
        "currency": "CHF",
        "language": "de",
        "ai_provider": "none",
        "anthropic_api_key": "",
        "anthropic_model": "claude-opus-4-6",
        "openai_api_key": "",
        "openai_model": "gpt-5.2",
        "openrouter_api_key": "",
        "openrouter_model": "anthropic/claude-opus-4.6",
        "ollama_host": "http://localhost:11434",
        "ollama_model": "llava",
    }
    try:
        with open(OPTIONS_PATH, "r") as f:
            opts = json.load(f)
        defaults.update(opts)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    # Backward compat: auto-detect Anthropic from old config (pre-multi-provider)
    if defaults.get("ai_provider", "none") == "none" and defaults.get("anthropic_api_key", "").strip():
        defaults["ai_provider"] = "anthropic"
    return defaults

def _is_ai_configured(opts):
    """Check if the selected AI provider is properly configured."""
    provider = opts.get("ai_provider", "none").strip().lower()
    if provider == "anthropic":
        return bool(opts.get("anthropic_api_key", "").strip())
    elif provider == "openai":
        return bool(opts.get("openai_api_key", "").strip())
    elif provider == "openrouter":
        return bool(opts.get("openrouter_api_key", "").strip())
    elif provider == "ollama":
        return bool(opts.get("ollama_host", "").strip())
    return False


HA_OPTIONS = load_options()

# Persist data in /share so it survives app restarts/updates
DATA_DIR = "/share/wine-tracker"
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "wine.db")

os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXT = {"jpg", "jpeg", "png", "webp", "gif"}
WINE_TYPES = ["Rotwein", "Weisswein", "Rosé", "Schaumwein", "Dessertwein", "Anderes"]

# ── Region → Coordinates lookup (for stats map) ──────────────────────────────
# Covers major wine countries and regions.  Keys are matched case-insensitively.
REGION_COORDS = {
    # Countries
    "frankreich":   [46.6, 2.2],   "france":      [46.6, 2.2],
    "italien":      [42.5, 12.5],  "italy":       [42.5, 12.5],  "italia":    [42.5, 12.5],
    "spanien":      [40.0, -3.7],  "spain":       [40.0, -3.7],  "españa":    [40.0, -3.7],
    "schweiz":      [46.8, 8.2],   "switzerland": [46.8, 8.2],   "suisse":    [46.8, 8.2],
    "deutschland":  [50.1, 8.7],   "germany":     [50.1, 8.7],
    "österreich":   [47.5, 14.5],  "austria":     [47.5, 14.5],
    "portugal":     [39.4, -8.2],
    "usa":          [38.5, -121.5], "vereinigte staaten": [38.5, -121.5],
    "argentinien":  [-33.4, -68.4], "argentina":  [-33.4, -68.4],
    "chile":        [-35.0, -71.2],
    "australien":   [-35.0, 138.5], "australia":  [-35.0, 138.5],
    "neuseeland":   [-41.3, 174.8], "new zealand": [-41.3, 174.8],
    "südafrika":    [-33.9, 18.9],  "south africa": [-33.9, 18.9],
    "griechenland": [38.5, 23.5],   "greece":     [38.5, 23.5],
    "ungarn":       [47.0, 19.5],   "hungary":    [47.0, 19.5],
    "georgien":     [42.0, 43.5],   "georgia":    [42.0, 43.5],
    "libanon":      [33.9, 35.5],   "lebanon":    [33.9, 35.5],
    "kroatien":     [45.1, 15.2],   "croatia":    [45.1, 15.2],
    "slowenien":    [46.1, 14.5],   "slovenia":   [46.1, 14.5],
    # French regions
    "bordeaux":     [44.8, -0.6],  "burgund":    [47.0, 4.8],    "bourgogne":  [47.0, 4.8],
    "champagne":    [49.0, 3.9],   "elsass":     [48.3, 7.4],    "alsace":     [48.3, 7.4],
    "loire":        [47.4, 0.7],   "rhône":      [44.9, 4.8],    "rhone":      [44.9, 4.8],
    "provence":     [43.5, 5.9],   "languedoc":  [43.3, 3.0],    "jura":       [46.7, 5.9],
    "beaujolais":   [46.1, 4.6],   "côtes du rhône": [44.3, 4.8],
    # Italian regions
    "toskana":      [43.4, 11.2],  "tuscany":    [43.4, 11.2],   "toscana":    [43.4, 11.2],
    "piemont":      [44.7, 8.0],   "piemonte":   [44.7, 8.0],    "piedmont":   [44.7, 8.0],
    "venetien":     [45.4, 12.3],  "veneto":     [45.4, 12.3],
    "sizilien":     [37.5, 14.0],  "sicilia":    [37.5, 14.0],   "sicily":     [37.5, 14.0],
    "sardinien":    [40.1, 9.1],   "sardegna":   [40.1, 9.1],
    "apulien":      [41.1, 16.9],  "puglia":     [41.1, 16.9],
    "abruzzen":     [42.2, 13.8],  "abruzzo":    [42.2, 13.8],
    "südtirol":     [46.5, 11.3],  "alto adige": [46.5, 11.3],
    "lombardei":    [45.5, 9.9],   "lombardia":  [45.5, 9.9],
    "kampanien":    [40.8, 14.3],  "campania":   [40.8, 14.3],
    "friaul":       [46.1, 13.2],  "friuli":     [46.1, 13.2],
    # Spanish regions
    "rioja":        [42.5, -2.5],  "ribera del duero": [41.6, -3.7],
    "priorat":      [41.2, 0.8],   "penedès":    [41.4, 1.7],
    "katalonien":   [41.6, 1.5],   "cataluña":   [41.6, 1.5],
    "galizien":     [42.5, -8.0],  "galicia":    [42.5, -8.0],
    "navarra":      [42.7, -1.6],
    # German regions
    "mosel":        [49.9, 6.9],   "rheingau":   [50.0, 8.0],
    "pfalz":        [49.3, 8.1],   "baden":      [48.0, 7.8],
    "franken":      [49.8, 10.0],  "rheinhessen": [49.8, 8.2],
    "ahr":          [50.5, 7.1],   "nahe":       [49.8, 7.6],
    "württemberg":  [48.8, 9.2],
    # Swiss regions
    "wallis":       [46.2, 7.6],   "valais":     [46.2, 7.6],
    "waadt":        [46.5, 6.6],   "vaud":       [46.5, 6.6],
    "genf":         [46.2, 6.1],   "genève":     [46.2, 6.1],
    "tessin":       [46.2, 8.9],   "ticino":     [46.2, 8.9],
    "graubünden":   [46.8, 9.8],   "schaffhausen": [47.7, 8.6],
    "zürich":       [47.4, 8.5],   "aargau":     [47.4, 8.1],
    # Austrian regions
    "wachau":       [48.4, 15.4],  "burgenland": [47.5, 16.5],
    "steiermark":   [46.9, 15.5],  "styria":     [46.9, 15.5],
    "niederösterreich": [48.2, 15.7], "wien":    [48.2, 16.4],
    # Portuguese regions
    "douro":        [41.2, -7.8],  "alentejo":   [38.5, -7.9],
    "dão":          [40.5, -7.9],  "minho":      [41.8, -8.3],
    # US regions
    "napa valley":  [38.5, -122.3], "napa":      [38.5, -122.3],
    "sonoma":       [38.3, -122.7], "kalifornien": [36.8, -119.4], "california": [36.8, -119.4],
    "oregon":       [45.2, -122.8], "washington": [46.8, -120.5],
    # South American regions
    "mendoza":      [-33.0, -68.8], "maipo":     [-33.7, -70.6],
    "colchagua":    [-34.7, -71.2], "casablanca": [-33.3, -71.4],
    # Australian regions
    "barossa":      [-34.5, 138.9], "barossa valley": [-34.5, 138.9],
    "mclaren vale": [-35.2, 138.5], "hunter valley":  [-32.8, 151.2],
    "margaret river": [-33.9, 115.0],
    # Others
    "tokaj":        [48.1, 21.4],  "stellenbosch": [-33.9, 18.8],
    "marlborough":  [-41.5, 174.0], "hawke's bay": [-39.5, 176.8],
}


# ── Ingress support ──────────────────────────────────────────────────────────
# HA Ingress proxies the app under /api/hassio_ingress/<token>/
# The header X-Ingress-Path tells us the prefix to use for all URLs.

@app.before_request
def set_ingress_path():
    g.ingress = request.headers.get("X-Ingress-Path", "")


# ── i18n ──────────────────────────────────────────────────────────────────────
LANG = HA_OPTIONS.get("language", "de")
T = TRANSLATIONS.get(LANG, TRANSLATIONS["de"])


@app.template_filter('wine_type')
def translate_wine_type(value):
    """Translate DB wine type (e.g. 'Rotwein') to the active language."""
    key = f"wine_type_{value}"
    return T.get(key, value)


@app.context_processor
def inject_globals():
    ai_enabled = _is_ai_configured(load_options())
    return {
        "ingress": g.get("ingress", ""),
        "currency": HA_OPTIONS.get("currency", "CHF"),
        "t": T,
        "lang": LANG,
        "ai_enabled": ai_enabled,
    }


def ingress_redirect(endpoint, **kwargs):
    """Redirect using the ingress-aware path."""
    path = g.get("ingress", "") + url_for(endpoint, **kwargs)
    return redirect(path)


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
                location     TEXT,
                grape        TEXT
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
            "grape":        "TEXT",
        }
        for col, dtype in migrations.items():
            if col not in existing:
                db.execute(f"ALTER TABLE wines ADD COLUMN {col} {dtype}")
        db.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

def geocode_region(region_name):
    """Look up lat/lon for a wine region. Returns [lat, lon] or None."""
    if not region_name:
        return None
    key = region_name.strip().lower()
    # Exact match first
    if key in REGION_COORDS:
        return REGION_COORDS[key]
    # Substring match – e.g. "Toskana, Italien" → finds "toskana"
    for name, coords in REGION_COORDS.items():
        if name in key or key in name:
            return coords
    return None


def is_ajax():
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def wine_json(wine_id):
    """Return a single wine row as JSON dict (for AJAX responses)."""
    db = get_db()
    row = db.execute("SELECT * FROM wines WHERE id=?", (wine_id,)).fetchone()
    if not row:
        return None
    return dict(row)


def stats_json():
    """Return current stats dict."""
    db = get_db()
    s = db.execute(
        "SELECT SUM(quantity) as total, COUNT(DISTINCT name) as types FROM wines WHERE quantity > 0"
    ).fetchone()
    return {"total": s["total"] or 0, "types": s["types"] or 0}


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
    wines = [dict(row) for row in db.execute(sql, params).fetchall()]

    stats = db.execute(
        "SELECT SUM(quantity) as total, COUNT(DISTINCT name) as types FROM wines WHERE quantity > 0"
    ).fetchone()

    # Only show filter tabs for types that actually exist in the DB
    used_types = [
        row[0] for row in db.execute(
            "SELECT DISTINCT type FROM wines WHERE type IS NOT NULL AND type != '' ORDER BY type"
        ).fetchall()
    ]

    # Distinct locations for datalist autocomplete
    used_locations = [
        row[0] for row in db.execute(
            "SELECT DISTINCT location FROM wines WHERE location IS NOT NULL AND location != '' ORDER BY location"
        ).fetchall()
    ]

    # Distinct grape varieties for datalist autocomplete
    used_grapes = [
        row[0] for row in db.execute(
            "SELECT DISTINCT grape FROM wines WHERE grape IS NOT NULL AND grape != '' ORDER BY grape"
        ).fetchall()
    ]

    return render_template(
        "index.html",
        wines=wines,
        wine_types=WINE_TYPES,
        used_types=used_types,
        used_locations=used_locations,
        used_grapes=used_grapes,
        query=q,
        active_type=t,
        show_empty=show_empty,
        stats=stats,
    )


@app.route("/add", methods=["POST"])
def add():
    db = get_db()
    image = save_image(request.files.get("image"))
    # If no new image uploaded but AI already saved one, use that
    if not image:
        ai_img = request.form.get("ai_image", "").strip()
        if ai_img and os.path.isfile(os.path.join(UPLOAD_DIR, ai_img)):
            image = ai_img
    price_raw = request.form.get("price", "").strip()
    cur = db.execute(
        """INSERT INTO wines
           (name, year, type, region, quantity, rating, notes, image, added,
            purchased_at, price, drink_from, drink_until, location, grape)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
            request.form.get("grape", "").strip() or None,
        ),
    )
    db.commit()
    new_id = cur.lastrowid
    if is_ajax():
        return jsonify({"ok": True, "wine": wine_json(new_id), "stats": stats_json()})
    path = g.get("ingress", "") + url_for("index") + f"?new={new_id}"
    return redirect(path)


@app.route("/edit/<int:wine_id>", methods=["POST"])
def edit(wine_id):
    db = get_db()
    wine = db.execute("SELECT * FROM wines WHERE id=?", (wine_id,)).fetchone()
    if not wine:
        return ingress_redirect("index")

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
           notes=?, image=?, purchased_at=?, price=?, drink_from=?, drink_until=?, location=?,
           grape=?
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
            request.form.get("grape", "").strip() or None,
            wine_id,
        ),
    )
    db.commit()
    if is_ajax():
        return jsonify({"ok": True, "wine": wine_json(wine_id), "stats": stats_json()})
    path = g.get("ingress", "") + url_for("index") + f"?new={wine_id}"
    return redirect(path)


@app.route("/duplicate/<int:wine_id>", methods=["POST"])
def duplicate(wine_id):
    db = get_db()
    wine = db.execute("SELECT * FROM wines WHERE id=?", (wine_id,)).fetchone()
    if not wine:
        return ingress_redirect("index")

    new_year = request.form.get("new_year") or wine["year"]

    # Copy image so each wine has its own independent file
    new_image = None
    if wine["image"]:
        src = os.path.join(UPLOAD_DIR, wine["image"])
        if os.path.exists(src):
            ext = wine["image"].rsplit(".", 1)[-1].lower()
            new_image = f"{uuid.uuid4().hex}.{ext}"
            shutil.copy2(src, os.path.join(UPLOAD_DIR, new_image))

    db.execute(
        """INSERT INTO wines (name, year, type, region, quantity, rating, notes, image, added,
           purchased_at, price, drink_from, drink_until, location, grape)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            wine["name"],
            new_year,
            wine["type"],
            wine["region"],
            int(request.form.get("quantity", wine["quantity"])),
            wine["rating"],
            wine["notes"],
            new_image,
            str(date.today()),
            wine["purchased_at"],
            wine["price"],
            wine["drink_from"],
            wine["drink_until"],
            wine["location"],
            wine["grape"],
        ),
    )
    db.commit()
    new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    if is_ajax():
        return jsonify({"ok": True, "wine": wine_json(new_id), "stats": stats_json()})
    return ingress_redirect("index")


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
    if is_ajax():
        return jsonify({"ok": True, "deleted": wine_id, "stats": stats_json()})
    return ingress_redirect("index")


@app.route("/stats")
def stats_page():
    db = get_db()
    from datetime import datetime
    current_year = datetime.now().year

    # Total bottles & distinct wines
    totals = db.execute(
        "SELECT SUM(quantity) as bottles, COUNT(*) as wines FROM wines"
    ).fetchone()

    # Bottles by type
    by_type = [dict(r) for r in db.execute(
        "SELECT type, SUM(quantity) as qty FROM wines WHERE type IS NOT NULL AND type != '' GROUP BY type ORDER BY qty DESC"
    ).fetchall()]

    # Top regions (bar chart – limited)
    top_regions = [dict(r) for r in db.execute(
        "SELECT region, SUM(quantity) as qty FROM wines WHERE region IS NOT NULL AND region != '' GROUP BY region ORDER BY qty DESC LIMIT 7"
    ).fetchall()]

    # All regions with coordinates (for the map)
    all_regions = [dict(r) for r in db.execute(
        "SELECT region, SUM(quantity) as qty FROM wines WHERE region IS NOT NULL AND region != '' GROUP BY region ORDER BY qty DESC"
    ).fetchall()]
    map_points = []
    for r in all_regions:
        coords = geocode_region(r["region"])
        if coords:
            map_points.append({"region": r["region"], "qty": r["qty"], "lat": coords[0], "lon": coords[1]})

    # Total value
    value = db.execute(
        "SELECT SUM(quantity * price) as total_value, AVG(price) as avg_price, "
        "MIN(price) as min_price, MAX(price) as max_price FROM wines WHERE price IS NOT NULL AND price > 0"
    ).fetchone()

    # Most expensive wine
    most_expensive = db.execute(
        "SELECT name, year, price FROM wines WHERE price IS NOT NULL ORDER BY price DESC LIMIT 1"
    ).fetchone()

    # Cheapest wine
    cheapest = db.execute(
        "SELECT name, year, price FROM wines WHERE price IS NOT NULL AND price > 0 ORDER BY price ASC LIMIT 1"
    ).fetchone()

    # Best rated wines
    best_rated = [dict(r) for r in db.execute(
        "SELECT name, year, type, rating, quantity FROM wines WHERE rating > 0 ORDER BY rating DESC, name LIMIT 5"
    ).fetchall()]

    # Average age
    avg_age = db.execute(
        f"SELECT AVG({current_year} - year) as avg_age FROM wines WHERE year IS NOT NULL AND year > 0"
    ).fetchone()

    # Oldest wine
    oldest = db.execute(
        "SELECT name, year, type FROM wines WHERE year IS NOT NULL AND year > 0 ORDER BY year ASC LIMIT 1"
    ).fetchone()

    # Newest wine
    newest = db.execute(
        "SELECT name, year, type FROM wines WHERE year IS NOT NULL AND year > 0 ORDER BY year DESC LIMIT 1"
    ).fetchone()

    # Recently added
    recent = [dict(r) for r in db.execute(
        "SELECT name, year, type, added FROM wines ORDER BY id DESC LIMIT 3"
    ).fetchall()]

    # Bottles in stock vs out
    in_stock = db.execute("SELECT SUM(quantity) FROM wines WHERE quantity > 0").fetchone()[0] or 0
    out_of_stock = db.execute("SELECT COUNT(*) FROM wines WHERE quantity = 0").fetchone()[0] or 0

    return render_template(
        "stats.html",
        totals=totals,
        by_type=by_type,
        top_regions=top_regions,
        map_points=map_points,
        value=value,
        most_expensive=dict(most_expensive) if most_expensive else None,
        cheapest=dict(cheapest) if cheapest else None,
        best_rated=best_rated,
        avg_age=avg_age["avg_age"] if avg_age else None,
        oldest=dict(oldest) if oldest else None,
        newest=dict(newest) if newest else None,
        recent=recent,
        in_stock=in_stock,
        out_of_stock=out_of_stock,
    )


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


# ── AI Provider Functions ─────────────────────────────────────────────────────

def _call_anthropic(image_b64, media_type, prompt, opts):
    """Call Anthropic Claude Vision API."""
    import anthropic
    api_key = opts.get("anthropic_api_key", "").strip()
    model = opts.get("anthropic_model", "claude-opus-4-6").strip() or "claude-opus-4-6"
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                {"type": "text", "text": prompt},
            ],
        }],
    )
    return message.content[0].text


def _call_openai(image_b64, media_type, prompt, opts):
    """Call OpenAI Vision API."""
    from openai import OpenAI
    api_key = opts.get("openai_api_key", "").strip()
    model = opts.get("openai_model", "gpt-5.2").strip() or "gpt-5.2"
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}},
                {"type": "text", "text": prompt},
            ],
        }],
        max_tokens=1024,
    )
    return response.choices[0].message.content


def _call_openrouter(image_b64, media_type, prompt, opts):
    """Call OpenRouter API (OpenAI-compatible with custom base_url)."""
    from openai import OpenAI
    api_key = opts.get("openrouter_api_key", "").strip()
    model = opts.get("openrouter_model", "anthropic/claude-opus-4.6").strip() or "anthropic/claude-opus-4.6"
    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )
    response = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}},
                {"type": "text", "text": prompt},
            ],
        }],
        max_tokens=1024,
    )
    return response.choices[0].message.content


def _call_ollama(image_b64, media_type, prompt, opts):
    """Call local Ollama Vision API."""
    import requests as req
    host = opts.get("ollama_host", "http://localhost:11434").strip().rstrip("/")
    model = opts.get("ollama_model", "llava").strip() or "llava"
    response = req.post(
        f"{host}/api/chat",
        json={
            "model": model,
            "messages": [{
                "role": "user",
                "content": prompt,
                "images": [image_b64],
            }],
            "stream": False,
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


# ── AI Wine Label Analysis ───────────────────────────────────────────────────

@app.route("/api/analyze-wine", methods=["POST"])
def analyze_wine():
    """Receive a wine label photo, save it, and call AI Vision to extract details."""
    import base64

    opts = load_options()
    provider = opts.get("ai_provider", "none").strip().lower()

    if provider == "none" or not _is_ai_configured(opts):
        return jsonify({"ok": False, "error": "no_api_key"}), 400

    file = request.files.get("image")
    if not file or not file.filename:
        return jsonify({"ok": False, "error": "no_image"}), 400

    # Save image first (persisted even if API fails)
    image_filename = save_image(file)
    if not image_filename:
        return jsonify({"ok": False, "error": "no_image"}), 400

    # Read saved file as base64
    image_path = os.path.join(UPLOAD_DIR, image_filename)
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    ext = image_filename.rsplit(".", 1)[1].lower()
    media_type = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "webp": "image/webp", "gif": "image/gif",
    }.get(ext, "image/jpeg")

    # Prompt is identical for all providers
    prompt = """Analyze this wine bottle label image. Extract the following fields and return ONLY valid JSON:
{
  "name": "wine name",
  "wine_type": "one of: Rotwein, Weisswein, Rosé, Schaumwein, Dessertwein, Anderes",
  "vintage": year as integer or null,
  "region": "wine region",
  "grape": "grape variety/varieties",
  "price": number or null,
  "drink_from": year as integer or null,
  "drink_until": year as integer or null,
  "notes": "brief tasting notes if visible on label"
}
Rules:
- wine_type MUST be exactly one of the 6 listed values
- vintage must be a 4-digit year or null
- drink_from/drink_until: drinking window years if mentioned on label, otherwise null
- price as number without currency symbol, or null if not visible
- If a field cannot be determined, set it to null or empty string
- Return ONLY the JSON object, no markdown, no explanation"""

    # Dispatch to the selected provider
    try:
        dispatch = {
            "anthropic": _call_anthropic,
            "openai": _call_openai,
            "openrouter": _call_openrouter,
            "ollama": _call_ollama,
        }
        call_fn = dispatch.get(provider)
        if not call_fn:
            return jsonify({"ok": False, "error": "invalid_provider", "image_filename": image_filename}), 400

        raw = call_fn(image_data, media_type, prompt, opts).strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3].strip()

        fields = json.loads(raw)

        # Validate wine_type
        if fields.get("wine_type") and fields["wine_type"] not in WINE_TYPES:
            fields["wine_type"] = ""

        return jsonify({"ok": True, "fields": fields, "image_filename": image_filename})

    except json.JSONDecodeError:
        app.logger.exception("AI analyze-wine JSON parse error")
        return jsonify({"ok": False, "error": "parse_error", "image_filename": image_filename}), 500
    except Exception as e:
        app.logger.exception("AI analyze-wine error: %s", e)
        error_msg = str(e)
        if "timeout" in error_msg.lower():
            return jsonify({"ok": False, "error": "timeout", "image_filename": image_filename}), 500
        return jsonify({"ok": False, "error": "api_error", "message": error_msg, "image_filename": image_filename}), 500


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
