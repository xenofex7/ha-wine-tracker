import json
import os
import secrets
import shutil
import sqlite3
import uuid
from collections import defaultdict
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, g, session
from werkzeug.security import generate_password_hash, check_password_hash
from translations import TRANSLATIONS

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# ── Authentication (optional, for standalone Docker deployment) ───────────────
# DEV_AUTH enables auth without a full HA setup: "user:pass" or "user:pass:role"
# Multiple users: "admin:pass:admin,viewer:pass:readonly"

def parse_user_string(raw):
    """Parse a user definition string into a dict of {username: {hash, role}}.

    Format: "user:pass" or "user:pass:role", comma-separated for multiple users.
    Default role is "admin" when omitted.
    """
    users = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if ":" in pair:
            parts = pair.split(":", 2)  # max 3 parts
            user = parts[0].strip()
            pw = parts[1].strip()
            role = parts[2].strip() if len(parts) > 2 else "admin"
            users[user] = {
                "hash": generate_password_hash(pw, method="pbkdf2:sha256"),
                "role": role,
            }
    return users


_dev_auth = os.environ.get("DEV_AUTH", "")
AUTH_ENABLED = os.environ.get("AUTH_ENABLED", "false").lower() == "true" or bool(_dev_auth.strip())

_users_raw = _dev_auth if _dev_auth.strip() else os.environ.get("USERS", "")
_USERS = parse_user_string(_users_raw) if AUTH_ENABLED else {}

# ── HA Add-on Options ─────────────────────────────────────────────────────────
OPTIONS_PATH = os.environ.get("OPTIONS_PATH", "/data/options.json")

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
        "minimax_api_key": "",
        "minimax_model": "MiniMax-Text-01",
    }
    try:
        with open(OPTIONS_PATH, "r") as f:
            opts = json.load(f)
        defaults.update(opts)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # ENV variables override options.json (for standalone Docker deployment)
    env_map = {
        "CURRENCY": "currency",
        "LANGUAGE": "language",
        "AI_PROVIDER": "ai_provider",
        "ANTHROPIC_API_KEY": "anthropic_api_key",
        "ANTHROPIC_MODEL": "anthropic_model",
        "OPENAI_API_KEY": "openai_api_key",
        "OPENAI_MODEL": "openai_model",
        "OPENROUTER_API_KEY": "openrouter_api_key",
        "OPENROUTER_MODEL": "openrouter_model",
        "OLLAMA_HOST": "ollama_host",
        "OLLAMA_MODEL": "ollama_model",
        "MINIMAX_API_KEY": "minimax_api_key",
        "MINIMAX_MODEL": "minimax_model",
    }
    for env_key, opt_key in env_map.items():
        val = os.environ.get(env_key)
        if val:
            defaults[opt_key] = val

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
    elif provider == "minimax":
        return bool(opts.get("minimax_api_key", "").strip())
    return False


def _ssl_verify():
    """Return best available CA bundle for requests verify parameter."""
    try:
        import certifi
        path = certifi.where()
        print(f"[SSL] Using certifi: {path}, exists={os.path.exists(path)}")
        return path
    except ImportError:
        print("[SSL] certifi not available, falling back to system certs")
        for p in ("/etc/ssl/certs/ca-certificates.crt", "/etc/ssl/cert.pem"):
            if os.path.exists(p):
                print(f"[SSL] Using system cert: {p}")
                return p
        print("[SSL] No CA bundle found, using requests default")
        return True


APP_VERSION = "1.9.1"

HA_OPTIONS = load_options()

# Persist data in /share so it survives app restarts/updates
# Falls /share nicht existiert (lokale Entwicklung), nutze ./data stattdessen
# DATA_DIR ENV override enables standalone Docker deployment
DATA_DIR = os.environ.get("DATA_DIR",
    "/share/wine-tracker" if os.path.isdir("/share")
    else os.path.join(os.path.dirname(__file__), "data"))
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "wine.db")

os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXT = {"jpg", "jpeg", "png", "webp", "gif"}
WINE_TYPES = ["Rotwein", "Weisswein", "Rosé", "Schaumwein", "Dessertwein", "Likörwein", "Anderes"]

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

WINE_LABELS = {
    "de": {
        "vintage":      "Jahrgang",
        "type":         "Typ",
        "region":       "Region",
        "grape":        "Rebsorte",
        "drink_window": "Trinkfenster",
        "notes":        "Notizen",
        "quantity":     "Menge",
        "bottles":      "Fl.",
        "rating":       "Bewertung",
        "location":     "Lagerort",
    },
    "en": {
        "vintage":      "Vintage",
        "type":         "Type",
        "region":       "Region",
        "grape":        "Grape variety",
        "drink_window": "Drinking window",
        "notes":        "Notes",
        "quantity":     "Quantity",
        "bottles":      "btl.",
        "rating":       "Rating",
        "location":     "Location",
    },
    "fr": {
        "vintage":      "Millésime",
        "type":         "Type",
        "region":       "Région",
        "grape":        "Cépage",
        "drink_window": "Fenêtre de dégustation",
        "notes":        "Notes",
        "quantity":     "Quantité",
        "bottles":      "btl.",
        "rating":       "Note",
        "location":     "Emplacement",
    },
    "it": {
        "vintage":      "Annata",
        "type":         "Tipo",
        "region":       "Regione",
        "grape":        "Vitigno",
        "drink_window": "Finestra di consumo",
        "notes":        "Note",
        "quantity":     "Quantità",
        "bottles":      "btl.",
        "rating":       "Valutazione",
        "location":     "Posizione",
    },
    "es": {
        "vintage":      "Añada",
        "type":         "Tipo",
        "region":       "Región",
        "grape":        "Variedad",
        "drink_window": "Ventana de consumo",
        "notes":        "Notas",
        "quantity":     "Cantidad",
        "bottles":      "bot.",
        "rating":       "Valoración",
        "location":     "Ubicación",
    },
    "pt": {
        "vintage":      "Colheita",
        "type":         "Tipo",
        "region":       "Região",
        "grape":        "Casta",
        "drink_window": "Janela de consumo",
        "notes":        "Notas",
        "quantity":     "Quantidade",
        "bottles":      "gf.",
        "rating":       "Avaliação",
        "location":     "Localização",
    },
    "nl": {
        "vintage":      "Oogstjaar",
        "type":         "Type",
        "region":       "Regio",
        "grape":        "Druivenras",
        "drink_window": "Drinkvenster",
        "notes":        "Notities",
        "quantity":     "Aantal",
        "bottles":      "fl.",
        "rating":       "Beoordeling",
        "location":     "Locatie",
    },
}

# ── Ingress support ──────────────────────────────────────────────────────────
# HA Ingress proxies the app under /api/hassio_ingress/<token>/
# The header X-Ingress-Path tells us the prefix to use for all URLs.

@app.before_request
def set_ingress_path():
    g.ingress = request.headers.get("X-Ingress-Path", "")


@app.before_request
def check_auth():
    """Enforce login when AUTH_ENABLED=true (standalone Docker deployment)."""
    if not AUTH_ENABLED:
        return
    if request.endpoint in ("login", "static", "uploaded_file"):
        return
    if not session.get("user"):
        if request.path.startswith("/api/"):
            return jsonify(ok=False, error="unauthorized"), 401
        return redirect(url_for("login"))


@app.before_request
def check_readonly():
    """Block write operations for readonly users."""
    if not AUTH_ENABLED:
        return
    if session.get("role") != "readonly":
        return
    if request.method in ("POST", "PUT", "DELETE"):
        # Allow login POST, chat API, chat sessions for readonly users
        # (session delete is blocked in the endpoint itself)
        allowed = {"login", "api_chat", "api_chat_sessions_list", "api_chat_session_detail"}
        if request.endpoint not in allowed:
            if request.is_json or request.headers.get("X-Requested-With"):
                return jsonify(ok=False, error="readonly"), 403
            return redirect(g.get("ingress", "") + "/")


# ── i18n ──────────────────────────────────────────────────────────────────────
LANG = HA_OPTIONS.get("language", "de")
T = TRANSLATIONS.get(LANG, TRANSLATIONS["de"])


@app.template_filter('wine_type')
def translate_wine_type(value):
    """Translate DB wine type (e.g. 'Rotwein') to the active language."""
    key = f"wine_type_{value}"
    return T.get(key, value)


@app.template_filter('format_date')
def format_date_filter(value):
    """Format ISO date string according to active language."""
    if not value:
        return ""
    try:
        d = date.fromisoformat(value)
    except (ValueError, TypeError):
        return value
    formats = {"de": "%d.%m.%Y", "fr": "%d/%m/%Y", "it": "%d/%m/%Y",
               "es": "%d/%m/%Y", "pt": "%d/%m/%Y", "nl": "%d-%m-%Y",
               "en": "%m/%d/%Y"}
    return d.strftime(formats.get(LANG, "%Y-%m-%d"))


@app.context_processor
def inject_globals():
    ai_enabled = _is_ai_configured(load_options())
    ctx = {
        "ingress": g.get("ingress", ""),
        "currency": HA_OPTIONS.get("currency", "CHF"),
        "t": T,
        "lang": LANG,
        "ai_enabled": ai_enabled,
        "auth_user": session.get("user") if AUTH_ENABLED else None,
        "auth_readonly": session.get("role") == "readonly" if AUTH_ENABLED else False,
        "app_version": APP_VERSION,
        "wine_types": WINE_TYPES,
    }
    # Provide form datalist values for the shared edit modal on every page
    try:
        db = get_db()
        ctx["used_regions_list"] = [
            row[0] for row in db.execute(
                "SELECT DISTINCT region FROM wines WHERE region IS NOT NULL AND region != '' ORDER BY region"
            ).fetchall()
        ]
        ctx["used_grapes"] = [
            row[0] for row in db.execute(
                "SELECT DISTINCT grape FROM wines WHERE grape IS NOT NULL AND grape != '' ORDER BY grape"
            ).fetchall()
        ]
        ctx["used_purchased_at"] = [
            row[0] for row in db.execute(
                "SELECT DISTINCT purchased_at FROM wines WHERE purchased_at IS NOT NULL AND purchased_at != '' ORDER BY purchased_at"
            ).fetchall()
        ]
        ctx["used_locations"] = [
            row[0] for row in db.execute(
                "SELECT DISTINCT location FROM wines WHERE location IS NOT NULL AND location != '' ORDER BY location"
            ).fetchall()
        ]
    except Exception:
        ctx.setdefault("used_regions_list", [])
        ctx.setdefault("used_grapes", [])
        ctx.setdefault("used_purchased_at", [])
        ctx.setdefault("used_locations", [])
    return ctx


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
            "purchased_at":   "TEXT",
            "price":          "REAL",
            "drink_from":     "INTEGER",
            "drink_until":    "INTEGER",
            "location":       "TEXT",
            "grape":          "TEXT",
            "vivino_id":      "INTEGER",
            "bottle_format":  "REAL DEFAULT 0.75",
            "maturity_data":  "TEXT",
            "taste_profile":  "TEXT",
            "food_pairings":  "TEXT",
        }
        for col, dtype in migrations.items():
            if col not in existing:
                db.execute(f"ALTER TABLE wines ADD COLUMN {col} {dtype}")

        # ── timeline table ────────────────────────────────────────────────
        db.execute("""
            CREATE TABLE IF NOT EXISTS timeline (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                wine_id   INTEGER NOT NULL,
                action    TEXT NOT NULL,
                quantity  INTEGER DEFAULT 1,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (wine_id) REFERENCES wines(id)
            )
        """)

        # Backfill: insert 'added' entries for existing wines (only on first migration)
        log_count = db.execute("SELECT COUNT(*) FROM timeline").fetchone()[0]
        if log_count == 0:
            wines = db.execute("SELECT id, quantity, added FROM wines").fetchall()
            for w in wines:
                ts = w[2] or date.today().isoformat()
                qty = w[1] if w[1] else 1
                db.execute(
                    "INSERT INTO timeline (wine_id, action, quantity, timestamp) VALUES (?,?,?,?)",
                    (w[0], "added", qty, ts),
                )

        # ── chat session tables ───────────────────────────────────────────
        db.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                title     TEXT,
                created   TEXT NOT NULL,
                updated   TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                timestamp  TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
            )
        """)

        # ── chat_messages migration: image_path ─────────────────────────
        chat_cols = {row[1] for row in db.execute("PRAGMA table_info(chat_messages)")}
        if "image_path" not in chat_cols:
            db.execute("ALTER TABLE chat_messages ADD COLUMN image_path TEXT")

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
    d = dict(row)
    # Parse JSON text columns into real objects
    for key in ("maturity_data", "taste_profile", "food_pairings"):
        raw = d.get(key)
        if raw:
            try:
                d[key] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                d[key] = None
    return d


def stats_json():
    """Return current stats dict."""
    db = get_db()
    s = db.execute(
        "SELECT SUM(quantity) as total, COUNT(DISTINCT name) as types FROM wines WHERE quantity > 0"
    ).fetchone()
    return {"total": s["total"] or 0, "types": s["types"] or 0}


def allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


MAX_IMAGE_PX = 1800  # downscale images so longest edge ≤ this


def _downscale(filepath):
    """Resize an image file in-place so its longest edge ≤ MAX_IMAGE_PX."""
    try:
        from PIL import Image, ImageOps
        with Image.open(filepath) as img:
            img = ImageOps.exif_transpose(img)
            w, h = img.size
            if max(w, h) <= MAX_IMAGE_PX:
                img.save(filepath, quality=85, optimize=True)
                return
            ratio = MAX_IMAGE_PX / max(w, h)
            new_size = (int(w * ratio), int(h * ratio))
            img = img.resize(new_size, Image.LANCZOS)
            img.save(filepath, quality=85, optimize=True)
    except Exception as e:
        app.logger.warning("Image downscale failed: %s", e)


def _downscale_bytes(file_storage):
    """Read an uploaded image, resize in memory, return (base64_str, media_type)."""
    import base64
    from io import BytesIO
    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                  "png": "image/png", "webp": "image/webp",
                  "gif": "image/gif"}.get(ext, "image/jpeg")
    try:
        from PIL import Image, ImageOps
        with Image.open(file_storage.stream) as img:
            img = ImageOps.exif_transpose(img)
            w, h = img.size
            if max(w, h) > MAX_IMAGE_PX:
                ratio = MAX_IMAGE_PX / max(w, h)
                img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
            buf = BytesIO()
            fmt = "JPEG" if ext in ("jpg", "jpeg") else ext.upper()
            if fmt == "WEBP":
                img.save(buf, format=fmt, quality=85)
            else:
                img.save(buf, format=fmt, quality=85, optimize=True)
            buf.seek(0)
            return base64.standard_b64encode(buf.read()).decode("utf-8"), media_type
    except Exception as e:
        app.logger.warning("Image downscale_bytes failed: %s", e)
        # Fallback: read raw bytes
        file_storage.stream.seek(0)
        raw = file_storage.stream.read()
        return base64.standard_b64encode(raw).decode("utf-8"), media_type


def save_image(file):
    if file and file.filename and allowed(file.filename):
        ext = file.filename.rsplit(".", 1)[1].lower()
        fname = f"{uuid.uuid4().hex}.{ext}"
        path = os.path.join(UPLOAD_DIR, fname)
        file.save(path)
        _downscale(path)
        return fname
    return None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if not AUTH_ENABLED:
        return redirect("/")
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        user_data = _USERS.get(username)
        if user_data and check_password_hash(user_data["hash"], password):
            session["user"] = username
            session["role"] = user_data["role"]
            return redirect(g.get("ingress", "") + "/")
        return render_template("login.html", error=True)
    return render_template("login.html", error=False)


@app.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("role", None)
    return redirect(url_for("login"))


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

    return render_template(
        "index.html",
        wines=wines,
        used_types=used_types,
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
    vivino_raw = request.form.get("vivino_id", "").strip()
    bottle_format_raw = request.form.get("bottle_format", "").strip()
    maturity_data_raw = request.form.get("maturity_data", "").strip() or None
    taste_profile_raw = request.form.get("taste_profile", "").strip() or None
    food_pairings_raw = request.form.get("food_pairings", "").strip() or None
    cur = db.execute(
        """INSERT INTO wines
           (name, year, type, region, quantity, rating, notes, image, added,
            purchased_at, price, drink_from, drink_until, location, grape, vivino_id, bottle_format,
            maturity_data, taste_profile, food_pairings)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
            int(vivino_raw) if vivino_raw else None,
            float(bottle_format_raw) if bottle_format_raw else 0.75,
            maturity_data_raw,
            taste_profile_raw,
            food_pairings_raw,
        ),
    )
    db.commit()
    new_id = cur.lastrowid
    # Log the addition
    qty = int(request.form.get("quantity", 1))
    db.execute(
        "INSERT INTO timeline (wine_id, action, quantity, timestamp) VALUES (?,?,?,?)",
        (new_id, "added", qty, datetime.now().isoformat()),
    )
    db.commit()
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
    if request.form.get("delete_image") == "1":
        if image:
            try:
                os.remove(os.path.join(UPLOAD_DIR, image))
            except FileNotFoundError:
                pass
        image = None
    new_image = save_image(request.files.get("image"))
    if new_image:
        # Remove old image
        if image:
            try:
                os.remove(os.path.join(UPLOAD_DIR, image))
            except FileNotFoundError:
                pass
        image = new_image
    # If no file upload but AI/Vivino downloaded an image, use that
    if not new_image:
        ai_img = request.form.get("ai_image", "").strip()
        if ai_img and ai_img != image and os.path.isfile(os.path.join(UPLOAD_DIR, ai_img)):
            if image:
                try:
                    os.remove(os.path.join(UPLOAD_DIR, image))
                except FileNotFoundError:
                    pass
            image = ai_img

    old_quantity = wine["quantity"] or 0
    price_raw = request.form.get("price", "").strip()
    vivino_raw = request.form.get("vivino_id", "").strip()
    bottle_format_raw = request.form.get("bottle_format", "").strip()
    # For enrichment fields: if the form submission doesn't carry the key at
    # all (e.g. quantity +/- buttons build a minimal FormData), keep whatever
    # is already stored in the DB instead of wiping it. An explicitly present
    # but empty key — as sent by the edit modal's hidden inputs — still clears.
    if "maturity_data" in request.form:
        maturity_data_raw = request.form.get("maturity_data", "").strip() or None
    else:
        maturity_data_raw = wine["maturity_data"]
    if "taste_profile" in request.form:
        taste_profile_raw = request.form.get("taste_profile", "").strip() or None
    else:
        taste_profile_raw = wine["taste_profile"]
    if "food_pairings" in request.form:
        food_pairings_raw = request.form.get("food_pairings", "").strip() or None
    else:
        food_pairings_raw = wine["food_pairings"]
    new_quantity = int(request.form.get("quantity", 0))
    db.execute(
        """UPDATE wines SET name=?, year=?, type=?, region=?, quantity=?, rating=?,
           notes=?, image=?, purchased_at=?, price=?, drink_from=?, drink_until=?, location=?,
           grape=?, vivino_id=?, bottle_format=?,
           maturity_data=?, taste_profile=?, food_pairings=?
           WHERE id=?""",
        (
            request.form["name"].strip(),
            request.form.get("year") or None,
            request.form.get("type"),
            request.form.get("region", "").strip(),
            new_quantity,
            int(request.form.get("rating", 0)),
            request.form.get("notes", "").strip(),
            image,
            request.form.get("purchased_at", "").strip() or None,
            float(price_raw) if price_raw else None,
            request.form.get("drink_from") or None,
            request.form.get("drink_until") or None,
            request.form.get("location", "").strip() or None,
            request.form.get("grape", "").strip() or None,
            int(vivino_raw) if vivino_raw else None,
            float(bottle_format_raw) if bottle_format_raw else 0.75,
            maturity_data_raw,
            taste_profile_raw,
            food_pairings_raw,
            wine_id,
        ),
    )
    # Log quantity changes
    if new_quantity < old_quantity:
        db.execute(
            "INSERT INTO timeline (wine_id, action, quantity, timestamp) VALUES (?,?,?,?)",
            (wine_id, "consumed", old_quantity - new_quantity, datetime.now().isoformat()),
        )
    elif new_quantity > old_quantity:
        db.execute(
            "INSERT INTO timeline (wine_id, action, quantity, timestamp) VALUES (?,?,?,?)",
            (wine_id, "restocked", new_quantity - old_quantity, datetime.now().isoformat()),
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
           purchased_at, price, drink_from, drink_until, location, grape, vivino_id, bottle_format,
           maturity_data, taste_profile, food_pairings)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
            wine["vivino_id"],
            wine["bottle_format"] if wine["bottle_format"] is not None else 0.75,
            wine["maturity_data"],
            wine["taste_profile"],
            wine["food_pairings"],
        ),
    )
    db.commit()
    new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    # Log the duplicated wine as added
    dup_qty = int(request.form.get("quantity", wine["quantity"]))
    db.execute(
        "INSERT INTO timeline (wine_id, action, quantity, timestamp) VALUES (?,?,?,?)",
        (new_id, "added", dup_qty, datetime.now().isoformat()),
    )
    db.commit()
    if is_ajax():
        return jsonify({"ok": True, "wine": wine_json(new_id), "stats": stats_json()})
    return ingress_redirect("index")


@app.route("/delete/<int:wine_id>", methods=["POST"])
def delete(wine_id):
    db = get_db()
    wine = db.execute("SELECT image, quantity FROM wines WHERE id=?", (wine_id,)).fetchone()
    # Log removal before deleting
    if wine:
        db.execute(
            "INSERT INTO timeline (wine_id, action, quantity, timestamp) VALUES (?,?,?,?)",
            (wine_id, "removed", wine["quantity"] or 0, datetime.now().isoformat()),
        )
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


@app.route("/chat")
def chat_page():
    opts = load_options()
    if not _is_ai_configured(opts):
        return ingress_redirect("index")
    return render_template("chat.html")


@app.route("/timeline")
def timeline_page():
    return render_template("timeline.html")


@app.route("/api/timeline")
def api_timeline():
    db = get_db()
    months_param = request.args.get("months")

    sql = """
        SELECT wl.id, wl.wine_id, w.name as wine_name, w.image as wine_image,
               w.type as wine_type, wl.action, wl.quantity, wl.timestamp
        FROM timeline wl
        LEFT JOIN wines w ON wl.wine_id = w.id
    """
    params = []
    if months_param:
        try:
            months = int(months_param)
            now = datetime.now()
            year = now.year
            month = now.month - months
            while month < 1:
                month += 12
                year -= 1
            cutoff = now.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)
            sql += " WHERE wl.timestamp >= ? "
            params.append(cutoff.isoformat())
        except (ValueError, TypeError):
            pass

    sql += " ORDER BY wl.timestamp DESC"

    rows = db.execute(sql, params).fetchall()

    # Group all entries with same wine_id + action + date (regardless of order)
    grouped = {}
    for r in rows:
        day = r["timestamp"][:10] if r["timestamp"] else ""
        # Chat entries are never grouped (each is a unique conversation)
        if r["action"] == "chat":
            key = ("chat", r["id"])
        else:
            key = (r["wine_id"], r["action"], day)
        if key in grouped:
            grouped[key]["quantity"] += r["quantity"]
        else:
            # For chat entries (wine_id=0), look up session title
            wine_name = r["wine_name"]
            if r["action"] == "chat" and r["wine_id"] == 0:
                # Try to get session title and id from the most recent chat session around this timestamp
                session_row = db.execute(
                    "SELECT id, title FROM chat_sessions WHERE created <= ? ORDER BY created DESC LIMIT 1",
                    (r["timestamp"],),
                ).fetchone()
                wine_name = session_row["title"] if session_row and session_row["title"] else T.get("log_chat", "Sommelier chat")
            elif not wine_name:
                wine_name = "(deleted)"
            entry = {
                "id": r["id"],
                "wine_id": r["wine_id"],
                "wine_name": wine_name,
                "wine_image": r["wine_image"],
                "wine_type": r["wine_type"],
                "action": r["action"],
                "quantity": r["quantity"],
                "timestamp": r["timestamp"],
            }
            if r["action"] == "chat" and session_row:
                entry["session_id"] = session_row["id"]
            grouped[key] = entry
    entries = sorted(grouped.values(), key=lambda e: e["timestamp"], reverse=True)
    return jsonify(ok=True, entries=entries)


@app.route("/stats")
def stats_page():
    db = get_db()
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

    # Total liters (quantity * bottle_format)
    total_liters = db.execute(
        "SELECT SUM(quantity * COALESCE(bottle_format, 0.75)) as liters FROM wines"
    ).fetchone()["liters"] or 0

    # Total value
    value = db.execute(
        "SELECT SUM(quantity * price) as total_value, AVG(price) as avg_price, "
        "MIN(price) as min_price, MAX(price) as max_price FROM wines WHERE price IS NOT NULL AND price > 0"
    ).fetchone()

    # Most expensive wine
    most_expensive = db.execute(
        "SELECT id, name, year, type, price FROM wines WHERE price IS NOT NULL ORDER BY price DESC LIMIT 1"
    ).fetchone()

    # Cheapest wine
    cheapest = db.execute(
        "SELECT id, name, year, type, price FROM wines WHERE price IS NOT NULL AND price > 0 ORDER BY price ASC LIMIT 1"
    ).fetchone()

    # Best rated wines
    best_rated = [dict(r) for r in db.execute(
        "SELECT id, name, year, type, rating, quantity FROM wines WHERE rating > 0 ORDER BY rating DESC, name LIMIT 5"
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
        "SELECT id, name, year, type, added FROM wines ORDER BY id DESC LIMIT 3"
    ).fetchall()]

    # Bottles in stock vs out
    in_stock = db.execute("SELECT SUM(quantity) FROM wines WHERE quantity > 0").fetchone()[0] or 0
    out_of_stock = db.execute("SELECT COUNT(*) FROM wines WHERE quantity = 0").fetchone()[0] or 0

    # Drink window chart – bottles per year, stacked by type
    dw_wines = [dict(r) for r in db.execute(
        "SELECT id, name, year, type, quantity, drink_from, drink_until FROM wines "
        "WHERE drink_until IS NOT NULL AND drink_until != '' AND quantity > 0"
    ).fetchall()]
    dw_by_year = defaultdict(lambda: defaultdict(int))
    dw_names_by_year = defaultdict(lambda: defaultdict(list))
    dw_types = set()
    for w in dw_wines:
        try:
            until = int(w["drink_until"])
            frm = int(w["drink_from"]) if w.get("drink_from") else until
            t = w["type"] or "Anderes"
            dw_types.add(t)
            entry = {"n": w["name"], "y": w.get("year"), "q": w["quantity"], "id": w["id"]}
            for yr in range(frm, until + 1):
                dw_by_year[yr][t] += w["quantity"]
                dw_names_by_year[yr][t].append(entry)
        except (ValueError, TypeError):
            pass
    if dw_by_year:
        dw_chart = [{"year": yr, "counts": dict(dw_by_year[yr])}
                    for yr in range(min(dw_by_year), max(dw_by_year) + 1)]
        dw_type_order = sorted(dw_types)
        dw_wine_names = {str(yr): {t: wl for t, wl in types.items()}
                         for yr, types in dw_names_by_year.items()}
    else:
        dw_chart = []
        dw_type_order = []
        dw_wine_names = {}

    # Stock history – last 6 months
    today = date.today()
    current_stock = totals["bottles"] or 0

    def month_add(y, m, n):
        m2 = m - 1 + n
        return y + m2 // 12, m2 % 12 + 1

    start_y, start_m = month_add(today.year, today.month, -6)
    first_of_six = date(start_y, start_m, 1)

    tl_rows = db.execute(
        "SELECT action, quantity, timestamp FROM timeline "
        "WHERE action IN ('added','consumed','restocked','removed') "
        "AND timestamp >= ? ORDER BY timestamp",
        (first_of_six.isoformat(),)
    ).fetchall()

    monthly_delta = defaultdict(lambda: {"added": 0, "consumed": 0, "restocked": 0, "removed": 0})
    for row in tl_rows:
        ts = row["timestamp"][:7]  # "YYYY-MM"
        monthly_delta[ts][row["action"]] += row["quantity"]

    months = []
    cy, cm = start_y, start_m
    ty, tm = today.year, today.month
    while (cy, cm) <= (ty, tm):
        months.append(f"{cy}-{cm:02d}")
        cy, cm = month_add(cy, cm, 1)

    total_net = 0
    for m in months:
        md = monthly_delta[m]
        total_net += md["added"] + md["restocked"] - md["consumed"] - md["removed"]
    start_stock = current_stock - total_net

    stock_chart = []
    running = start_stock
    month_names_short = {
        "de": ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"],
        "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "fr": ["Jan", "Fév", "Mar", "Avr", "Mai", "Jun", "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc"],
        "it": ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"],
        "es": ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"],
        "pt": ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"],
        "nl": ["Jan", "Feb", "Mrt", "Apr", "Mei", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dec"],
    }
    m_names = month_names_short.get(LANG, month_names_short["en"])
    for m in months:
        md = monthly_delta[m]
        net = md["added"] + md["restocked"] - md["consumed"] - md["removed"]
        running += net
        month_idx = int(m[5:7]) - 1
        year_short = m[2:4]
        stock_chart.append({
            "label": f"{m_names[month_idx]} {year_short}",
            "stock": max(running, 0),
            "added": md["added"] + md["restocked"],
            "consumed": md["consumed"] + md["removed"],
        })

    # Tooltip data – wine names grouped by type and region
    wines_by_type = {}
    for row in db.execute(
        "SELECT id, name, year, type, quantity FROM wines "
        "WHERE type IS NOT NULL AND type != '' AND quantity > 0 ORDER BY name"
    ).fetchall():
        wines_by_type.setdefault(row["type"], []).append(
            {"n": row["name"], "y": row["year"], "q": row["quantity"], "id": row["id"]})

    wines_by_region = {}
    for row in db.execute(
        "SELECT id, name, year, region, quantity FROM wines "
        "WHERE region IS NOT NULL AND region != '' AND quantity > 0 ORDER BY name"
    ).fetchall():
        wines_by_region.setdefault(row["region"], []).append(
            {"n": row["name"], "y": row["year"], "q": row["quantity"], "id": row["id"]})

    type_translations = {t: T.get(f"wine_type_{t}", t) for t in WINE_TYPES}

    return render_template(
        "stats.html",
        totals=totals,
        total_liters=total_liters,
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
        dw_chart=dw_chart,
        dw_type_order=dw_type_order,
        dw_wine_names=dw_wine_names,
        stock_chart=stock_chart,
        wines_by_type=wines_by_type,
        wines_by_region=wines_by_region,
        type_translations=type_translations,
        current_year=current_year,
    )


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    # Only serve files matching our naming pattern (uuid hex + allowed extension)
    if not filename or "/" in filename or "\\" in filename:
        return "Not found", 404
    parts = filename.rsplit(".", 1)
    if len(parts) != 2 or parts[1].lower() not in ALLOWED_EXT:
        return "Not found", 404
    return send_from_directory(UPLOAD_DIR, filename)


# ── AI Provider Functions ─────────────────────────────────────────────────────

def _call_anthropic(image_b64, media_type, prompt, opts):
    """Call Anthropic Claude API (vision or text-only)."""
    import anthropic
    api_key = opts.get("anthropic_api_key", "").strip()
    model = opts.get("anthropic_model", "claude-opus-4-6").strip() or "claude-opus-4-6"
    client = anthropic.Anthropic(api_key=api_key)
    content = []
    if image_b64:
        content.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}})
    content.append({"type": "text", "text": prompt})
    message = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": content}],
    )
    return message.content[0].text


def _call_openai(image_b64, media_type, prompt, opts):
    """Call OpenAI API (vision or text-only)."""
    from openai import OpenAI
    api_key = opts.get("openai_api_key", "").strip()
    model = opts.get("openai_model", "gpt-5.2").strip() or "gpt-5.2"
    client = OpenAI(api_key=api_key)
    content = []
    if image_b64:
        content.append({"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}})
    content.append({"type": "text", "text": prompt})
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        max_completion_tokens=1024,
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
    content = []
    if image_b64:
        content.append({"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}})
    content.append({"type": "text", "text": prompt})
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        max_completion_tokens=1024,
    )
    return response.choices[0].message.content


def _call_ollama(image_b64, media_type, prompt, opts):
    """Call local Ollama API (vision or text-only)."""
    import requests as req
    host = opts.get("ollama_host", "http://localhost:11434").strip().rstrip("/")
    model = opts.get("ollama_model", "llava").strip() or "llava"
    msg = {"role": "user", "content": prompt}
    if image_b64:
        msg["images"] = [image_b64]
    response = req.post(
        f"{host}/api/chat",
        json={"model": model, "messages": [msg], "stream": False},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


def _call_minimax(image_b64, media_type, prompt, opts):
    """Call MiniMax API (OpenAI-compatible, vision or text-only)."""
    from openai import OpenAI
    api_key = opts.get("minimax_api_key", "").strip()
    model = opts.get("minimax_model", "MiniMax-Text-01").strip() or "MiniMax-Text-01"
    client = OpenAI(api_key=api_key, base_url="https://api.minimaxi.chat/v1")
    content = []
    if image_b64:
        content.append({"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}})
    content.append({"type": "text", "text": prompt})
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        max_tokens=1024,
    )
    return response.choices[0].message.content


# ── AI Chat Functions ─────────────────────────────────────────────────────────

def _call_chat_anthropic(messages, system_prompt, opts, image_b64=None, media_type=None):
    """Chat via Anthropic Claude (multi-turn, with optional image)."""
    import anthropic
    api_key = opts.get("anthropic_api_key", "").strip()
    model = opts.get("anthropic_model", "claude-opus-4-6").strip() or "claude-opus-4-6"
    client = anthropic.Anthropic(api_key=api_key)
    # Attach image to the last user message if provided
    if image_b64 and messages:
        last = messages[-1]
        if last["role"] == "user":
            messages = messages[:-1] + [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                {"type": "text", "text": last["content"]},
            ]}]
    message = client.messages.create(
        model=model,
        max_tokens=2048,
        system=system_prompt,
        messages=messages,
    )
    return message.content[0].text


def _call_chat_openai(messages, system_prompt, opts, image_b64=None, media_type=None):
    """Chat via OpenAI (multi-turn, with optional image)."""
    from openai import OpenAI
    api_key = opts.get("openai_api_key", "").strip()
    model = opts.get("openai_model", "gpt-5.2").strip() or "gpt-5.2"
    client = OpenAI(api_key=api_key)
    if image_b64 and messages:
        last = messages[-1]
        if last["role"] == "user":
            messages = messages[:-1] + [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}},
                {"type": "text", "text": last["content"]},
            ]}]
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    response = client.chat.completions.create(
        model=model,
        messages=full_messages,
        max_completion_tokens=2048,
    )
    return response.choices[0].message.content


def _call_chat_openrouter(messages, system_prompt, opts, image_b64=None, media_type=None):
    """Chat via OpenRouter (multi-turn, with optional image)."""
    from openai import OpenAI
    api_key = opts.get("openrouter_api_key", "").strip()
    model = opts.get("openrouter_model", "anthropic/claude-opus-4.6").strip() or "anthropic/claude-opus-4.6"
    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )
    if image_b64 and messages:
        last = messages[-1]
        if last["role"] == "user":
            messages = messages[:-1] + [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}},
                {"type": "text", "text": last["content"]},
            ]}]
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    response = client.chat.completions.create(
        model=model,
        messages=full_messages,
        max_completion_tokens=2048,
    )
    return response.choices[0].message.content


def _call_chat_ollama(messages, system_prompt, opts, image_b64=None, media_type=None):
    """Chat via local Ollama (multi-turn, with optional image)."""
    import requests as req
    host = opts.get("ollama_host", "http://localhost:11434").strip().rstrip("/")
    model = opts.get("ollama_model", "llava").strip() or "llava"
    if image_b64 and messages:
        last = messages[-1]
        if last["role"] == "user":
            messages = messages[:-1] + [{"role": "user", "content": last["content"], "images": [image_b64]}]
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    response = req.post(
        f"{host}/api/chat",
        json={"model": model, "messages": full_messages, "stream": False},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


def _call_chat_minimax(messages, system_prompt, opts, image_b64=None, media_type=None):
    """Chat via MiniMax (OpenAI-compatible, multi-turn, with optional image)."""
    from openai import OpenAI
    api_key = opts.get("minimax_api_key", "").strip()
    model = opts.get("minimax_model", "MiniMax-Text-01").strip() or "MiniMax-Text-01"
    client = OpenAI(api_key=api_key, base_url="https://api.minimaxi.chat/v1")
    if image_b64 and messages:
        last = messages[-1]
        if last["role"] == "user":
            messages = messages[:-1] + [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}},
                {"type": "text", "text": last["content"]},
            ]}]
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    response = client.chat.completions.create(
        model=model,
        messages=full_messages,
        max_tokens=2048,
    )
    return response.choices[0].message.content


def _call_chat(provider, messages, system_prompt, opts, image_b64=None, media_type=None):
    """Dispatch chat to the configured AI provider."""
    dispatch = {
        "anthropic": _call_chat_anthropic,
        "openai": _call_chat_openai,
        "openrouter": _call_chat_openrouter,
        "ollama": _call_chat_ollama,
        "minimax": _call_chat_minimax,
    }
    fn = dispatch.get(provider)
    if not fn:
        raise ValueError(f"Unknown chat provider: {provider}")
    return fn(messages, system_prompt, opts, image_b64=image_b64, media_type=media_type)


def _build_wine_cellar_context():
    """Fetch all in-stock wines and format as structured text for the AI system prompt."""

    labels = WINE_LABELS.get(LANG, WINE_LABELS['en'])
    db = get_db()
    wines = db.execute(
        "SELECT * FROM wines WHERE quantity > 0 ORDER BY type, name, year"
    ).fetchall()
    if not wines:
        return "", 0
    lines = []
    for w in wines:
        w = dict(w)
        parts = [f"- [ID:{w['id']}] {w['name']}"]
        if w.get("year"):
            parts.append(f"{labels['vintage']} {w['year']}")
        if w.get("type"):
            parts.append(f"{labels['type']}: {w['type']}")
        if w.get("region"):
            parts.append(f"{labels['region']}: {w['region']}")
        if w.get("grape"):
            parts.append(f"{labels['grape']}: {w['grape']}")
        if w.get("quantity"):
            parts.append(f"{labels['quantity']}: {w['quantity']} {labels['bottles']}")
        if w.get("rating"):
            parts.append(f"{labels['rating']}: {w['rating']}/5")
        if w.get("location"):
            parts.append(f"{labels['location']}: {w['location']}")
        if w.get("drink_from") or w.get("drink_until"):
            parts.append(
                f"{labels['drink_window']}: {w.get('drink_from', '?')}-{w.get('drink_until', '?')}"
            )
        if w.get("notes"):
            parts.append(f"{labels['notes']}: {w['notes']}")
        lines.append(" | ".join(parts))
    return "\n".join(lines), len(wines)

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
    lang_names = {"de": "German", "en": "English", "fr": "French", "it": "Italian",
                  "es": "Spanish", "pt": "Portuguese", "nl": "Dutch"}
    lang_name = lang_names.get(LANG, "English")
    prompt = f"""Analyze this wine bottle label image. Extract the following fields and return ONLY valid JSON:
{{
  "name": "wine name",
  "wine_type": "one of: Rotwein, Weisswein, Rosé, Schaumwein, Dessertwein, Likörwein, Anderes",
  "vintage": year as integer or null,
  "region": "wine region",
  "grape": "grape variety/varieties",
  "price": number or null,
  "drink_from": year as integer or null,
  "drink_until": year as integer or null,
  "notes": "brief tasting notes if visible on label",
  "bottle_format": number or null,
  "maturity_data": {{
    "youth": [start_year, end_year],
    "maturity": [start_year, end_year],
    "peak": [start_year, end_year],
    "decline": [start_year, end_year]
  }},
  "taste_profile": {{
    "body": 1-5,
    "tannin": 1-5,
    "acidity": 1-5,
    "sweetness": 1-5
  }},
  "food_pairings": ["dish1", "dish2", "dish3"]
}}
Rules:
- wine_type MUST be exactly one of the listed values
- vintage must be a 4-digit year or null
- drink_from/drink_until: drinking window years. If mentioned on label, use those. Otherwise ESTIMATE a reasonable drinking window based on the wine type, grape variety, region, and vintage using your wine expertise. For example, a simple Pinot Grigio 2023 might be 2024-2026, while a Barolo 2018 might be 2025-2035. Only return null if you cannot determine enough about the wine to estimate.
- price as number without currency symbol, or null if not visible
- bottle_format: volume in liters as number (e.g. 0.75, 1.5, 0.375). Only set if clearly visible on the label. Valid values: 0.1875, 0.375, 0.75, 1.5, 3, 4.5, 6, 9, 12, 15. Return null if not clearly identifiable (do NOT guess).
- maturity_data: Estimate the 4 maturity phases (youth, maturity, peak, decline) as year ranges based on wine type, grape, region, and vintage. Youth = early years after bottling, maturity = developing complexity, peak = optimal drinking, decline = past prime. Set to null if vintage is null or unknown.
- taste_profile: Estimate body (light 1 to full 5), tannin (low 1 to high 5), acidity (low 1 to high 5), sweetness (dry 1 to sweet 5) based on wine type and grape variety. Set to null if wine type is unknown.
- food_pairings: Suggest 3-5 food pairings based on the wine type and characteristics. Write food names in {lang_name}. Set to null if wine type is unknown.
- If a field cannot be determined, set it to null or empty string
- The "notes" and "food_pairings" fields MUST be written in {lang_name}
- Return ONLY the JSON object, no markdown, no explanation"""

    # Dispatch to the selected provider
    try:
        dispatch = {
            "anthropic": _call_anthropic,
            "openai": _call_openai,
            "openrouter": _call_openrouter,
            "ollama": _call_ollama,
            "minimax": _call_minimax,
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


# ── Vivino Wine Search ──────────────────────────────────────────────────────

VIVINO_WINE_TYPES = {1: "Rotwein", 2: "Weisswein", 3: "Schaumwein", 4: "Rosé", 7: "Dessertwein", 24: "Likörwein"}

def _vivino_country_code(currency):
    """Map currency to Vivino country/currency codes."""
    mapping = {
        "CHF": ("CH", "CHF"), "EUR": ("DE", "EUR"), "USD": ("US", "USD"),
        "GBP": ("GB", "GBP"), "CAD": ("CA", "CAD"), "AUD": ("AU", "AUD"),
        "SEK": ("SE", "SEK"), "NOK": ("NO", "NOK"), "DKK": ("DK", "DKK"),
        "PLN": ("PL", "PLN"), "CZK": ("CZ", "CZK"), "BRL": ("BR", "BRL"),
    }
    return mapping.get(currency, ("US", "USD"))


# Vivino search endpoint fallback chain. The default endpoint is fine for many
# queries but for some queries and for some user geolocations (notably users
# in Australia) Vivino redirects /search/wines to /<lang>/explore — an entirely
# different client-rendered page that does not contain the data-preloaded-state
# JSON we parse. The Italian and Spanish locale prefixes consistently render
# the classic search page with results, so we use them as fallbacks when the
# primary query misses. Ordered by empirical hit rate.
VIVINO_SEARCH_URLS = (
    "https://www.vivino.com/search/wines",
    "https://www.vivino.com/it/search/wines",
    "https://www.vivino.com/es/search/wines",
)


@app.route("/api/vivino-search")
def vivino_search():
    """Search wines on Vivino by scraping their search page.

    The Vivino explore API no longer supports free-text search (returns 400
    "At least one filter should be set").  The web search page, however,
    embeds its results as JSON inside a ``data-preloaded-state`` attribute
    on the ``#search-page`` div — we parse that instead.
    """
    import html as htmlmod
    import re
    import requests as req

    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify({"ok": False, "error": "query_too_short"}), 400

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html",
    }

    # Try each endpoint in the fallback chain until one returns matches.
    # Some queries and some user geolocations get redirected to the /explore
    # page which uses a different client-side rendered layout — we detect
    # that and fall through to the next endpoint.
    data = None
    last_error = None
    try:
        for url in VIVINO_SEARCH_URLS:
            try:
                resp = req.get(
                    url,
                    params={"q": query},
                    headers=headers,
                    timeout=10,
                    verify=_ssl_verify(),
                    allow_redirects=True,
                )
                resp.raise_for_status()
            except req.exceptions.Timeout:
                last_error = "timeout"
                continue
            except Exception as e:
                last_error = str(e)
                continue

            # If we got bounced to /explore, the JSON blob we need isn't there
            if "/explore" in resp.url:
                continue

            m = re.search(r'data-preloaded-state="([^"]+)"', resp.text)
            if not m:
                continue
            candidate = json.loads(htmlmod.unescape(m.group(1)))
            matches = candidate.get("search_results", {}).get("matches", [])
            if matches:
                data = candidate
                break
            # First endpoint explicitly returned 0 matches — keep trying
            # fallbacks in case another regional catalogue has the wine.
            if data is None:
                data = candidate  # remember as "empty but valid" fallback

    except Exception as e:
        app.logger.exception("Vivino search error: %s", e)
        return jsonify({"ok": False, "error": "api_error"}), 502

    if data is None:
        if last_error == "timeout":
            return jsonify({"ok": False, "error": "timeout"}), 504
        return jsonify({"ok": False, "error": "parse_error"}), 502

    results = []
    try:
        for match in data.get("search_results", {}).get("matches", []):
            vintage = match.get("vintage", {})
            wine = vintage.get("wine", {}) or {}
            winery = wine.get("winery", {}) or {}
            region = wine.get("region", {}) or {}
            country_obj = region.get("country", {}) or {}

            # Grape varieties
            grapes = []
            for g_item in wine.get("grapes", []) or []:
                grape_obj = g_item.get("grape", {}) or {}
                if grape_obj.get("name"):
                    grapes.append(grape_obj["name"])

            # Price
            price_obj = match.get("price", {}) or {}
            price_val = price_obj.get("amount")

            # Wine type
            wine_type_id = wine.get("type_id")
            wine_type = VIVINO_WINE_TYPES.get(wine_type_id, "Anderes") if wine_type_id else ""

            # Region string
            region_name = region.get("name", "")
            country_name = country_obj.get("name", "")
            region_str = f"{region_name}, {country_name}" if region_name and country_name else region_name or country_name

            # Image
            image_url = vintage.get("image", {}).get("location", "") if vintage.get("image") else ""

            results.append({
                "vivino_id": wine.get("id"),
                "name": f"{winery.get('name', '')} {wine.get('name', '')}".strip(),
                "year": vintage.get("year") or None,
                "wine_type": wine_type,
                "region": region_str,
                "grape": ", ".join(grapes),
                "rating": round(vintage.get("statistics", {}).get("wine_ratings_average", 0), 1) or None,
                "price": round(price_val, 2) if price_val else None,
                "image_url": image_url,
            })
    except Exception as e:
        app.logger.exception("Vivino parse error: %s", e)
        return jsonify({"ok": False, "error": "parse_error"}), 502

    return jsonify({"ok": True, "results": results})


@app.route("/api/vivino-image", methods=["POST"])
def vivino_image():
    """Download a Vivino wine image and save it locally."""
    import requests as req
    from urllib.parse import urlparse

    body = request.get_json(silent=True) or {}
    url = body.get("url", "").strip()
    if not url:
        return jsonify({"ok": False, "error": "no_url"}), 400
    # Protocol-relative URLs (//images.vivino.com/...) need a scheme
    if url.startswith("//"):
        url = "https:" + url

    # SSRF protection: only allow Vivino image domains
    ALLOWED_HOSTS = {"images.vivino.com", "pictures.vivino.com"}
    parsed = urlparse(url)
    if parsed.hostname not in ALLOWED_HOSTS:
        return jsonify({"ok": False, "error": "invalid_host"}), 400

    try:
        resp = req.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        }, verify=_ssl_verify())
        resp.raise_for_status()
        # Determine extension from content-type
        ct = resp.headers.get("Content-Type", "image/jpeg")
        ext = "jpg"
        if "png" in ct:
            ext = "png"
        elif "webp" in ct:
            ext = "webp"
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(resp.content)
        _downscale(filepath)
        return jsonify({"ok": True, "filename": filename})
    except Exception as e:
        app.logger.exception("Vivino image download error: %s", e)
        return jsonify({"ok": False, "error": "download_failed"}), 500


# ── AI Re-analysis (image, text, or both) ─────────────────────────────────────

def _wine_json_schema():
    return """{
  "name": "wine name",
  "wine_type": "one of: Rotwein, Weisswein, Rosé, Schaumwein, Dessertwein, Likörwein, Anderes",
  "vintage": year as integer or null,
  "region": "wine region",
  "grape": "grape variety/varieties",
  "price": number or null,
  "drink_from": year as integer or null,
  "drink_until": year as integer or null,
  "notes": "brief tasting notes",
  "bottle_format": number or null,
  "maturity_data": {"youth": [start_year, end_year], "maturity": [start_year, end_year], "peak": [start_year, end_year], "decline": [start_year, end_year]},
  "taste_profile": {"body": 1-5, "tannin": 1-5, "acidity": 1-5, "sweetness": 1-5},
  "food_pairings": ["dish1", "dish2", "dish3"]
}"""


def _wine_json_rules(lang="en"):
    lang_names = {"de": "German", "en": "English", "fr": "French", "it": "Italian",
                  "es": "Spanish", "pt": "Portuguese", "nl": "Dutch"}
    lang_name = lang_names.get(lang, "English")
    return f"""Rules:
- wine_type MUST be exactly one of the listed values
- vintage must be a 4-digit year or null
- drink_from/drink_until: estimate a reasonable drinking window based on wine type, grape, region, and vintage using your wine expertise. For example, a simple Pinot Grigio 2023 might be 2024-2026, while a Barolo 2018 might be 2025-2035. Only return null if you cannot determine enough about the wine to estimate.
- price as number without currency symbol, or null
- bottle_format: volume in liters as number (e.g. 0.75, 1.5, 0.375). Only set if clearly visible on the label. Valid values: 0.1875, 0.375, 0.75, 1.5, 3, 4.5, 6, 9, 12, 15. Return null if not clearly identifiable (do NOT guess).
- maturity_data: Estimate the 4 maturity phases (youth, maturity, peak, decline) as year ranges based on wine type, grape, region, and vintage. Youth = early years after bottling, maturity = developing complexity, peak = optimal drinking, decline = past prime. Set to null if vintage is null or unknown.
- taste_profile: Estimate body (light 1 to full 5), tannin (low 1 to high 5), acidity (low 1 to high 5), sweetness (dry 1 to sweet 5) based on wine type and grape variety. Set to null if wine type is unknown.
- food_pairings: Suggest 3-5 food pairings based on the wine type and characteristics. Write food names in {lang_name}. Set to null if wine type is unknown.
- If a field cannot be determined, set it to null or empty string
- The "notes" and "food_pairings" fields MUST be written in {lang_name}
- Return ONLY the JSON object, no markdown, no explanation"""


def _load_image_b64(image_filename):
    """Load an image from UPLOAD_DIR and return (b64, media_type) or (None, 'image/jpeg')."""
    import base64

    if not image_filename:
        return None, "image/jpeg"
    image_path = os.path.join(UPLOAD_DIR, image_filename)
    if not os.path.isfile(image_path):
        return None, "image/jpeg"
    with open(image_path, "rb") as f:
        image_b64 = base64.standard_b64encode(f.read()).decode("utf-8")
    ext = image_filename.rsplit(".", 1)[-1].lower() if "." in image_filename else "jpg"
    media_type = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "webp": "image/webp", "gif": "image/gif",
    }.get(ext, "image/jpeg")
    return image_b64, media_type


def _analyze_wine_from_context(opts, image_b64, media_type, wine_context):
    """Call the configured AI provider to extract/enrich wine fields.

    Returns a dict of wine fields (may be partial), or raises on error.
    Accepts image, text context, or both. Used by both the /api/reanalyze-wine
    HTTP endpoint and the chat ADD_WINE enrichment pass.
    """
    context_parts = []
    if wine_context.get("name"):   context_parts.append(f"Name: {wine_context['name']}")
    if wine_context.get("year"):   context_parts.append(f"Vintage: {wine_context['year']}")
    if wine_context.get("type"):   context_parts.append(f"Type: {wine_context['type']}")
    if wine_context.get("region"): context_parts.append(f"Region: {wine_context['region']}")
    if wine_context.get("grape"):  context_parts.append(f"Grape: {wine_context['grape']}")

    if not image_b64 and not context_parts:
        raise ValueError("no_data")

    schema = _wine_json_schema()
    rules = _wine_json_rules(LANG)

    if image_b64 and context_parts:
        ctx = "\n".join(context_parts)
        prompt = f"Analyze this wine bottle label image. The user already knows:\n{ctx}\n\nExtract/verify the following fields and return ONLY valid JSON:\n{schema}\n{rules}"
    elif image_b64:
        prompt = f"Analyze this wine bottle label image. Extract the following fields and return ONLY valid JSON:\n{schema}\n{rules}"
    else:
        ctx = "\n".join(context_parts)
        prompt = f"Based on the following wine information, fill in as many missing details as possible using your wine expertise. Known information:\n{ctx}\n\nReturn ONLY valid JSON with these fields (fill in what you can determine):\n{schema}\n{rules}"

    provider = opts.get("ai_provider", "none").strip().lower()
    dispatch = {
        "anthropic": _call_anthropic,
        "openai": _call_openai,
        "openrouter": _call_openrouter,
        "ollama": _call_ollama,
        "minimax": _call_minimax,
    }
    call_fn = dispatch.get(provider)
    if not call_fn:
        raise ValueError("invalid_provider")

    raw = call_fn(image_b64, media_type, prompt, opts).strip()

    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw[:-3].strip()

    fields = json.loads(raw)

    if fields.get("wine_type") and fields["wine_type"] not in WINE_TYPES:
        fields["wine_type"] = ""

    return fields


@app.route("/api/reanalyze-wine", methods=["POST"])
def reanalyze_wine():
    """Re-analyze a wine using image, text context, or both."""
    opts = load_options()
    provider = opts.get("ai_provider", "none").strip().lower()

    if provider == "none" or not _is_ai_configured(opts):
        return jsonify({"ok": False, "error": "no_api_key"}), 400

    body = request.get_json(silent=True) or {}
    image_filename = (body.get("image_filename") or "").strip()
    wine_context = body.get("wine_context") or {}

    image_b64, media_type = _load_image_b64(image_filename)

    try:
        fields = _analyze_wine_from_context(opts, image_b64, media_type, wine_context)
        return jsonify({"ok": True, "fields": fields})

    except ValueError as e:
        code = str(e)
        if code in ("no_data", "invalid_provider"):
            return jsonify({"ok": False, "error": code}), 400
        raise
    except json.JSONDecodeError:
        app.logger.exception("AI reanalyze-wine JSON parse error")
        return jsonify({"ok": False, "error": "parse_error"}), 500
    except Exception as e:
        app.logger.exception("AI reanalyze-wine error: %s", e)
        error_msg = str(e)
        if "timeout" in error_msg.lower():
            return jsonify({"ok": False, "error": "timeout"}), 500
        return jsonify({"ok": False, "error": "api_error", "message": error_msg}), 500



# ── Chat Session API ──────────────────────────────────────────────────────────

@app.route("/api/chat/sessions", methods=["GET", "POST"])
def api_chat_sessions_list():
    """List all chat sessions or create a new one."""
    db = get_db()

    if request.method == "GET":
        rows = db.execute("""
            SELECT cs.id, cs.title, cs.created, cs.updated,
                   COUNT(cm.id) as message_count
            FROM chat_sessions cs
            LEFT JOIN chat_messages cm ON cm.session_id = cs.id
            GROUP BY cs.id
            ORDER BY cs.updated DESC
        """).fetchall()
        sessions = [dict(r) for r in rows]
        return jsonify(ok=True, sessions=sessions)

    # POST – create new session
    now = datetime.now().isoformat()
    cur = db.execute(
        "INSERT INTO chat_sessions (title, created, updated) VALUES (?, ?, ?)",
        (None, now, now),
    )
    db.commit()
    session_id = cur.lastrowid

    # Log to timeline
    db.execute(
        "INSERT INTO timeline (wine_id, action, quantity, timestamp) VALUES (?, ?, ?, ?)",
        (0, "chat", 1, now),
    )
    db.commit()

    return jsonify(ok=True, session={
        "id": session_id,
        "title": None,
        "created": now,
        "updated": now,
    })


@app.route("/api/chat/sessions/<int:session_id>", methods=["GET", "DELETE"])
def api_chat_session_detail(session_id):
    """Get or delete a single chat session."""
    db = get_db()

    if request.method == "GET":
        sess = db.execute(
            "SELECT * FROM chat_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not sess:
            return jsonify(ok=False, error="not_found"), 404
        messages = db.execute(
            "SELECT id, role, content, timestamp, image_path FROM chat_messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        msg_list = []
        for m in messages:
            d = dict(m)
            # image_path is relative (e.g. "chat/1/abc.jpg"),
            # frontend builds full URL with INGRESS prefix
            msg_list.append(d)
        return jsonify(ok=True, session=dict(sess), messages=msg_list)

    # DELETE
    if AUTH_ENABLED and session.get("role") == "readonly":
        return jsonify(ok=False, error="readonly"), 403
    sess = db.execute(
        "SELECT id FROM chat_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if not sess:
        return jsonify(ok=False, error="not_found"), 404
    # Delete chat image folder
    import shutil
    chat_img_dir = os.path.join(UPLOAD_DIR, "chat", str(session_id))
    if os.path.isdir(chat_img_dir):
        shutil.rmtree(chat_img_dir, ignore_errors=True)
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
    db.commit()
    return jsonify(ok=True)


# ── AI Wine Chat ──────────────────────────────────────────────────────────────


def _process_chat_add_wine(response_text, session_id, session_images, db):
    """Parse [ADD_WINE] block from AI response, create the wine, copy the image."""
    import json as _json
    import re as _re
    import shutil

    match = _re.search(r'\[ADD_WINE\]\s*(\{.*?\})\s*\[/ADD_WINE\]', response_text, _re.DOTALL)
    if not match:
        return None
    try:
        data = _json.loads(match.group(1))
    except (ValueError, _json.JSONDecodeError):
        return None

    name = (data.get("name") or "").strip()
    if not name:
        return None

    # Validate wine type
    wine_type = data.get("wine_type", "Anderes")
    if wine_type not in WINE_TYPES:
        wine_type = "Anderes"

    # Handle image: copy from chat uploads to wine uploads
    wine_image = None
    image_index = data.get("image_index")
    if image_index and session_images:
        idx = int(image_index) - 1  # 0-based
        if 0 <= idx < len(session_images):
            src_path = os.path.join(UPLOAD_DIR, session_images[idx]["image_path"])
            if os.path.isfile(src_path):
                ext = os.path.splitext(src_path)[1] or ".jpg"
                wine_image = uuid.uuid4().hex + ext
                dst_path = os.path.join(UPLOAD_DIR, wine_image)
                shutil.copy2(src_path, dst_path)

    now = str(date.today())
    year = data.get("year")
    if year:
        try:
            year = int(year)
        except (ValueError, TypeError):
            year = None

    price = data.get("price", 0)
    try:
        price = float(price) if price else 0
    except (ValueError, TypeError):
        price = 0

    rating = data.get("rating", 0)
    try:
        rating = int(rating) if rating else 0
        rating = max(0, min(5, rating))
    except (ValueError, TypeError):
        rating = 0

    quantity = data.get("quantity", 1)
    try:
        quantity = int(quantity) if quantity else 1
    except (ValueError, TypeError):
        quantity = 1

    drink_from = data.get("drink_from")
    drink_until = data.get("drink_until")
    try:
        drink_from = int(drink_from) if drink_from else None
    except (ValueError, TypeError):
        drink_from = None
    try:
        drink_until = int(drink_until) if drink_until else None
    except (ValueError, TypeError):
        drink_until = None

    db.execute(
        """INSERT INTO wines
           (name, year, type, region, quantity, rating, notes, image, added,
            purchased_at, price, drink_from, drink_until, location, grape, vivino_id, bottle_format)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            name,
            year,
            wine_type,
            data.get("region", ""),
            quantity,
            rating,
            data.get("notes", ""),
            wine_image,
            now,
            data.get("purchased_at", ""),
            price,
            drink_from,
            drink_until,
            data.get("location", ""),
            data.get("grape", ""),
            None,  # vivino_id
            0.75,  # bottle_format
        ),
    )
    db.commit()
    wine_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Log to timeline
    db.execute(
        "INSERT INTO timeline (wine_id, action, quantity, timestamp) VALUES (?, ?, ?, ?)",
        (wine_id, "added", quantity, datetime.now().isoformat()),
    )
    db.commit()

    # Enrichment pass: the chat ADD_WINE block is intentionally small and
    # doesn't include maturity_data/taste_profile/food_pairings. Run the same
    # AI analysis used by the "Reload" button so the new wine gets the full
    # maturity graph, taste profile and food pairings out of the box.
    try:
        opts = load_options()
        if opts.get("ai_provider", "none").strip().lower() != "none" and _is_ai_configured(opts):
            image_b64, media_type = _load_image_b64(wine_image)
            wine_ctx = {
                "name":   name,
                "year":   year,
                "type":   wine_type,
                "region": data.get("region", ""),
                "grape":  data.get("grape", ""),
            }
            enriched = _analyze_wine_from_context(opts, image_b64, media_type, wine_ctx)

            updates = []
            params = []
            maturity = enriched.get("maturity_data")
            if maturity:
                updates.append("maturity_data = ?")
                params.append(json.dumps(maturity))
            taste = enriched.get("taste_profile")
            if taste:
                updates.append("taste_profile = ?")
                params.append(json.dumps(taste))
            pairings = enriched.get("food_pairings")
            if pairings:
                updates.append("food_pairings = ?")
                params.append(json.dumps(pairings))
            # Only fill drink window from enrichment if the chat didn't supply one
            if drink_from is None and enriched.get("drink_from"):
                try:
                    updates.append("drink_from = ?")
                    params.append(int(enriched["drink_from"]))
                except (ValueError, TypeError):
                    pass
            if drink_until is None and enriched.get("drink_until"):
                try:
                    updates.append("drink_until = ?")
                    params.append(int(enriched["drink_until"]))
                except (ValueError, TypeError):
                    pass

            if updates:
                params.append(wine_id)
                db.execute(
                    f"UPDATE wines SET {', '.join(updates)} WHERE id = ?",
                    params,
                )
                db.commit()
    except Exception as e:
        app.logger.warning("Chat ADD_WINE enrichment failed for wine %s: %s", wine_id, e)

    return {"action": "added", "id": wine_id, "name": name, "year": year, "type": wine_type}


def _process_chat_edit_wine(response_text, db):
    """Parse [EDIT_WINE] block from AI response, update the wine in DB."""
    import json as _json
    import re as _re

    match = _re.search(r'\[EDIT_WINE\]\s*(\{.*?\})\s*\[/EDIT_WINE\]', response_text, _re.DOTALL)
    if not match:
        return None
    try:
        data = _json.loads(match.group(1))
    except (ValueError, _json.JSONDecodeError):
        return None

    wine_id = data.get("id")
    if not wine_id:
        return None
    try:
        wine_id = int(wine_id)
    except (ValueError, TypeError):
        return None

    wine = db.execute("SELECT * FROM wines WHERE id = ?", (wine_id,)).fetchone()
    if not wine:
        return None

    # Build update fields - only update what's provided
    updates = {}
    field_map = {
        "name": str, "region": str, "grape": str, "notes": str,
        "location": str, "purchased_at": str,
    }
    for field, cast in field_map.items():
        if field in data and data[field] is not None:
            updates[field] = cast(data[field])

    if "year" in data:
        try:
            updates["year"] = int(data["year"]) if data["year"] else None
        except (ValueError, TypeError):
            pass
    if "wine_type" in data:
        wt = data["wine_type"]
        if wt in WINE_TYPES:
            updates["type"] = wt
    if "quantity" in data:
        try:
            new_qty = int(data["quantity"])
            old_qty = wine["quantity"] or 0
            updates["quantity"] = new_qty
            # Log quantity changes
            if new_qty < old_qty:
                db.execute(
                    "INSERT INTO timeline (wine_id, action, quantity, timestamp) VALUES (?, ?, ?, ?)",
                    (wine_id, "consumed", old_qty - new_qty, datetime.now().isoformat()),
                )
            elif new_qty > old_qty:
                db.execute(
                    "INSERT INTO timeline (wine_id, action, quantity, timestamp) VALUES (?, ?, ?, ?)",
                    (wine_id, "restocked", new_qty - old_qty, datetime.now().isoformat()),
                )
        except (ValueError, TypeError):
            pass
    if "rating" in data:
        try:
            updates["rating"] = max(0, min(5, int(data["rating"])))
        except (ValueError, TypeError):
            pass
    if "price" in data:
        try:
            updates["price"] = float(data["price"]) if data["price"] else 0
        except (ValueError, TypeError):
            pass
    for df in ("drink_from", "drink_until"):
        if df in data:
            try:
                updates[df] = int(data[df]) if data[df] else None
            except (ValueError, TypeError):
                pass

    if not updates:
        return None

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [wine_id]
    db.execute(f"UPDATE wines SET {set_clause} WHERE id = ?", values)
    db.commit()

    return {
        "action": "edited",
        "id": wine_id,
        "name": updates.get("name", wine["name"]),
        "year": updates.get("year", wine["year"]),
        "fields": list(updates.keys()),
    }


def _process_chat_delete_wine(response_text, db):
    """Parse [DELETE_WINE] block from AI response, delete the wine from DB."""
    import json as _json
    import re as _re

    match = _re.search(r'\[DELETE_WINE\]\s*(\{.*?\})\s*\[/DELETE_WINE\]', response_text, _re.DOTALL)
    if not match:
        return None
    try:
        data = _json.loads(match.group(1))
    except (ValueError, _json.JSONDecodeError):
        return None

    wine_id = data.get("id")
    if not wine_id:
        return None
    try:
        wine_id = int(wine_id)
    except (ValueError, TypeError):
        return None

    wine = db.execute("SELECT * FROM wines WHERE id = ?", (wine_id,)).fetchone()
    if not wine:
        return None

    wine_name = wine["name"]
    wine_year = wine["year"]
    wine_qty = wine["quantity"] or 0

    # Delete wine image if exists
    if wine["image"]:
        img_path = os.path.join(UPLOAD_DIR, wine["image"])
        if os.path.isfile(img_path):
            os.remove(img_path)

    db.execute("DELETE FROM wines WHERE id = ?", (wine_id,))
    # Log to timeline
    if wine_qty > 0:
        db.execute(
            "INSERT INTO timeline (wine_id, action, quantity, timestamp) VALUES (?, ?, ?, ?)",
            (wine_id, "removed", wine_qty, datetime.now().isoformat()),
        )
    db.commit()

    return {"action": "deleted", "id": wine_id, "name": wine_name, "year": wine_year}


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Wine sommelier chat – AI answers questions about the user's wine cellar."""
    opts = load_options()
    provider = opts.get("ai_provider", "none").strip().lower()
    if provider == "none" or not _is_ai_configured(opts):
        return jsonify({"ok": False, "error": "ai_not_configured"}), 400

    # Support both JSON and multipart/form-data (for image uploads)
    image_b64 = None
    media_type = None
    edit_wines = False
    if request.content_type and "multipart/form-data" in request.content_type:
        user_message = (request.form.get("message") or "").strip()
        import json as _json
        history = _json.loads(request.form.get("history", "[]"))
        session_id = request.form.get("session_id", type=int)
        save_raw = request.form.get("save", "true")
        save = save_raw.lower() != "false"
        edit_wines = request.form.get("edit_wines", "false").lower() == "true"
        # Process uploaded image
        img_file = request.files.get("image")
        if img_file and img_file.filename and allowed(img_file.filename):
            image_b64, media_type = _downscale_bytes(img_file)
    else:
        body = request.get_json(silent=True) or {}
        user_message = (body.get("message") or "").strip()
        history = body.get("history") or []
        session_id = body.get("session_id")
        save = body.get("save", True)
        edit_wines = body.get("edit_wines", False)

    if not user_message:
        return jsonify({"ok": False, "error": "empty_message"}), 400

    db = get_db()
    now = datetime.now().isoformat()
    saved_image_path = None

    if save:
        # Auto-create session if none provided
        if not session_id:
            cur = db.execute(
                "INSERT INTO chat_sessions (title, created, updated) VALUES (?, ?, ?)",
                (user_message[:50], now, now),
            )
            db.commit()
            session_id = cur.lastrowid
            # Log to timeline
            db.execute(
                "INSERT INTO timeline (wine_id, action, quantity, timestamp) VALUES (?, ?, ?, ?)",
                (0, "chat", 1, now),
            )
            db.commit()
        else:
            # Verify session exists
            sess = db.execute("SELECT id, title FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
            if not sess:
                return jsonify({"ok": False, "error": "session_not_found"}), 404
            # Auto-generate title from first user message if title is empty
            if not sess["title"]:
                db.execute(
                    "UPDATE chat_sessions SET title = ? WHERE id = ?",
                    (user_message[:50], session_id),
                )

        # Save user message to DB (with optional image)
        saved_image_path = None
        if image_b64 and session_id:
            import base64 as _b64
            ext_map = {"image/jpeg": ".jpg", "image/png": ".png",
                       "image/webp": ".webp", "image/gif": ".gif"}
            ext = ext_map.get(media_type, ".jpg")
            chat_dir = os.path.join(UPLOAD_DIR, "chat", str(session_id))
            os.makedirs(chat_dir, exist_ok=True)
            fname = uuid.uuid4().hex + ext
            fpath = os.path.join(chat_dir, fname)
            with open(fpath, "wb") as f:
                f.write(_b64.b64decode(image_b64))
            saved_image_path = f"chat/{session_id}/{fname}"
        db.execute(
            "INSERT INTO chat_messages (session_id, role, content, timestamp, image_path) VALUES (?, ?, ?, ?, ?)",
            (session_id, "user", user_message, now, saved_image_path),
        )
        db.commit()

        # If no history provided, load from DB
        if not history:
            db_msgs = db.execute(
                "SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
            # Exclude the just-inserted user message (it's the last one)
            history = [{"role": m["role"], "content": m["content"]} for m in db_msgs[:-1]]

    # Limit conversation history to prevent token overflow
    history = history[-20:]

    # Validate history: only user/assistant roles allowed (block system-role injection)
    valid_history = []
    for msg in history:
        if isinstance(msg, dict) and msg.get("role") in ("user", "assistant") and msg.get("content"):
            valid_history.append({"role": msg["role"], "content": msg["content"]})

    # Build wine cellar context
    cellar_text, wine_count = _build_wine_cellar_context()

    lang_map = {
        "de": "German", "en": "English", "fr": "French", "it": "Italian",
        "es": "Spanish", "pt": "Portuguese", "nl": "Dutch",
    }
    lang_name = lang_map.get(LANG, "English")

    system_prompt = (
        f"You are an expert wine sommelier and personal wine advisor. "
        f"You have deep knowledge of the user's wine cellar.\n\n"
        f"ALWAYS respond in {lang_name}.\n\n"
        f"The user's wine cellar currently contains {wine_count} wines (only in-stock bottles):\n"
        f"{cellar_text if cellar_text else '(The cellar is currently empty.)'}\n\n"
        f"Your capabilities:\n"
        f"- Recommend wines from the cellar for specific dishes, occasions, or moods\n"
        f"- Suggest food pairings for specific wines in the cellar\n"
        f"- Answer questions about wines, regions, grape varieties, and winemaking\n"
        f"- Give advice on drinking windows and when to open specific bottles\n"
        f"- Compare wines in the cellar\n"
        f"- Suggest what wines to buy to complement the collection\n"
        f"- Analyze wine label images the user sends you — identify the wine, describe it, and give recommendations\n\n"
        f"Rules:\n"
        f"- When recommending wines, ALWAYS pick from the user's cellar first\n"
        f"- If no wine in the cellar fits, say so and suggest what to buy\n"
        f"- Be concise but informative\n"
        f"- Use a friendly, knowledgeable tone\n"
        f"- If the user asks about a wine not in their cellar, you can still answer with general expertise\n"
        f"- When mentioning a wine FROM THE CELLAR, format it as a markdown link: [Wine Name Vintage](wine:ID) where ID is the number from [ID:…] in the cellar data\n"
        f"- Example: [Château Margaux 2015](wine:42)\n"
        f"- Only use wine: links for wines that exist in the cellar with an ID; for purchase suggestions use plain text"
    )

    # Extend system prompt with wine editing capabilities
    if edit_wines and not (AUTH_ENABLED and session.get("role") == "readonly"):
        # List images uploaded in this chat session
        session_images = []
        if session_id:
            img_rows = db.execute(
                "SELECT id, image_path, content FROM chat_messages "
                "WHERE session_id = ? AND image_path IS NOT NULL ORDER BY id",
                (session_id,),
            ).fetchall()
            for idx, row in enumerate(img_rows, 1):
                session_images.append({
                    "index": idx,
                    "image_path": row["image_path"],
                    "context": (row["content"] or "")[:80],
                })
        # Also count the current upload as the next image
        if image_b64 and saved_image_path:
            session_images.append({
                "index": len(session_images) + 1,
                "image_path": saved_image_path,
                "context": user_message[:80],
            })

        images_info = ""
        if session_images:
            img_lines = []
            for img in session_images:
                img_lines.append(f"  Image {img['index']}: {img['image_path']} (context: {img['context']})")
            images_info = (
                f"\n\nImages uploaded in this conversation:\n"
                + "\n".join(img_lines)
            )

        system_prompt += (
            f"\n\n--- WINE EDITING MODE ---\n"
            f"The user has enabled wine editing. You can ADD, EDIT, and DELETE wines in the cellar.\n"
            f"When the user asks you to manage wines, output the appropriate action block.\n\n"
            f"GENERAL RULES:\n"
            f"- ALWAYS confirm with the user before ANY action — show them the details and ask for confirmation\n"
            f"- Only output action blocks AFTER the user has confirmed\n"
            f"- wine_type MUST be one of: Rotwein, Weisswein, Rosé, Schaumwein, Dessertwein, Likörwein, Anderes\n"
            f"- You can only perform ONE action per message\n\n"
            f"=== ADD WINE ===\n"
            f"Fill in as many fields as possible from the conversation and label photos.\n"
            f"If multiple images were uploaded, ask the user which image to use.\n"
            f"[ADD_WINE]\n"
            f'{{"name": "Wine Name", "year": 2020, "wine_type": "Rotwein", "region": "Region, Country", '
            f'"grape": "Grape Variety", "quantity": 1, "rating": 0, "notes": "Tasting notes", '
            f'"price": 0, "drink_from": null, "drink_until": null, "location": "", '
            f'"image_index": 1}}\n'
            f"[/ADD_WINE]\n"
            f"- image_index: which uploaded image to use (1-based), or null for no image\n\n"
            f"=== EDIT WINE ===\n"
            f"Use the wine ID from [ID:...] in the cellar data. Only include fields that should change.\n"
            f"[EDIT_WINE]\n"
            f'{{"id": 42, "year": 2021, "quantity": 3, "rating": 4}}\n'
            f"[/EDIT_WINE]\n"
            f"- Supported fields: name, year, wine_type, region, grape, quantity, rating, notes, price, drink_from, drink_until, location, purchased_at\n\n"
            f"=== DELETE WINE ===\n"
            f"Use the wine ID from [ID:...] in the cellar data. Be VERY careful — always double-confirm deletion.\n"
            f"[DELETE_WINE]\n"
            f'{{"id": 42}}\n'
            f"[/DELETE_WINE]"
            f"{images_info}"
        )

    messages = valid_history + [{"role": "user", "content": user_message}]

    try:
        response_text = _call_chat(provider, messages, system_prompt, opts,
                                    image_b64=image_b64, media_type=media_type)

        # Check if AI wants to perform wine actions
        wine_action = None
        if edit_wines:
            import re as _re
            if "[ADD_WINE]" in response_text and "[/ADD_WINE]" in response_text:
                wine_action = _process_chat_add_wine(
                    response_text, session_id, session_images, db
                )
            elif "[EDIT_WINE]" in response_text and "[/EDIT_WINE]" in response_text:
                wine_action = _process_chat_edit_wine(response_text, db)
            elif "[DELETE_WINE]" in response_text and "[/DELETE_WINE]" in response_text:
                wine_action = _process_chat_delete_wine(response_text, db)

            # Remove any action blocks from the displayed response
            response_text = _re.sub(
                r'\[(ADD|EDIT|DELETE)_WINE\].*?\[/\1_WINE\]', '', response_text, flags=_re.DOTALL
            ).strip()

        if save:
            # Save assistant response to DB
            db.execute(
                "INSERT INTO chat_messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, "assistant", response_text, datetime.now().isoformat()),
            )
            # Update session timestamp
            db.execute(
                "UPDATE chat_sessions SET updated = ? WHERE id = ?",
                (datetime.now().isoformat(), session_id),
            )
            db.commit()

        result = {"ok": True, "response": response_text}
        if save and session_id:
            result["session_id"] = session_id
        if wine_action:
            result["wine_action"] = wine_action
        return jsonify(result)
    except Exception as e:
        app.logger.exception("Chat error: %s", e)
        error_msg = str(e)
        if "timeout" in error_msg.lower():
            return jsonify({"ok": False, "error": "timeout"}), 500
        return jsonify({"ok": False, "error": "api_error", "message": error_msg}), 500

# ── API for Home Assistant sensors ───────────────────────────────────────────

@app.route("/api/wine/<int:wine_id>")
def api_get_wine(wine_id):
    db = get_db()
    wine = db.execute("SELECT * FROM wines WHERE id = ?", (wine_id,)).fetchone()
    if not wine:
        return jsonify({"ok": False, "error": "not found"}), 404
    return jsonify({"ok": True, "wine": wine_json(wine_id)})


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
