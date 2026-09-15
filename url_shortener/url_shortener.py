"""
SwiftLink — Modern Flask URL Shortener & Analytics
-------------------------------------------------
Converts long URLs into short codes, tracks visit clicks, generates QR codes,
and provides a responsive glassmorphism dashboard UI.

Run:
    python url_shortener.py
"""

import sqlite3
import string
import secrets
import threading
import webbrowser
import re
from pathlib import Path
from urllib.parse import urlparse
from flask import Flask, request, render_template, redirect, jsonify, url_for

PROJECT_DIR = Path(__file__).resolve().parent
DB_FILE = str(PROJECT_DIR / "url_shortener.db")
CODE_LENGTH = 6
ALPHABET = string.ascii_letters + string.digits


def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize SQLite DB and perform automatic schema migration."""
    conn = get_db()
    with conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS urls (
                   code TEXT PRIMARY KEY,
                   original_url TEXT NOT NULL,
                   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                   clicks INTEGER DEFAULT 0
               )"""
        )
        # Migration check for legacy database schemas
        cursor = conn.execute("PRAGMA table_info(urls)")
        columns = [row["name"] for row in cursor.fetchall()]
        if "created_at" not in columns:
            conn.execute("ALTER TABLE urls ADD COLUMN created_at TIMESTAMP")
            conn.execute("UPDATE urls SET created_at = datetime('now') WHERE created_at IS NULL")
        if "clicks" not in columns:
            conn.execute("ALTER TABLE urls ADD COLUMN clicks INTEGER DEFAULT 0")
    conn.close()


def generate_code(conn):
    """Generate a unique random short code."""
    while True:
        code = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
        exists = conn.execute("SELECT 1 FROM urls WHERE code = ?", (code,)).fetchone()
        if not exists:
            return code


def shorten_url(original_url, custom_code=None):
    original_url = original_url.strip()
    if not original_url:
        raise ValueError("URL cannot be empty")

    if not original_url.startswith(("http://", "https://")):
        original_url = "https://" + original_url

    parsed_url = urlparse(original_url)
    if not parsed_url.netloc or "." not in parsed_url.netloc:
        raise ValueError("Please enter a valid website URL (e.g., https://example.com)")

    conn = get_db()
    try:
        with conn:
            if custom_code:
                custom_code = custom_code.strip()
                if not re.match(r"^[a-zA-Z0-9_-]{3,20}$", custom_code):
                    raise ValueError("Custom alias must be 3-20 characters long (letters, numbers, -, _)")
                
                exists = conn.execute("SELECT 1 FROM urls WHERE code = ?", (custom_code,)).fetchone()
                if exists:
                    raise ValueError(f"Custom alias '{custom_code}' is already taken.")
                code = custom_code
            else:
                # Reuse code if same URL already shortened without custom alias
                row = conn.execute("SELECT code FROM urls WHERE original_url = ?", (original_url,)).fetchone()
                if row:
                    return row["code"]
                code = generate_code(conn)

            conn.execute(
                "INSERT INTO urls (code, original_url, clicks) VALUES (?, ?, 0)",
                (code, original_url),
            )
            return code
    finally:
        conn.close()


def resolve_and_track_code(code):
    """Resolve short code to original URL and increment click count."""
    conn = get_db()
    try:
        with conn:
            row = conn.execute("SELECT original_url FROM urls WHERE code = ?", (code,)).fetchone()
            if row:
                conn.execute("UPDATE urls SET clicks = clicks + 1 WHERE code = ?", (code,))
                return row["original_url"]
            return None
    finally:
        conn.close()


def get_all_links():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT code, original_url, COALESCE(created_at, datetime('now', 'localtime')) as created_at, clicks FROM urls ORDER BY rowid DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_stats():
    conn = get_db()
    try:
        total_links = conn.execute("SELECT COUNT(*) FROM urls").fetchone()[0]
        total_clicks = conn.execute("SELECT SUM(clicks) FROM urls").fetchone()[0] or 0
        return total_links, total_clicks
    finally:
        conn.close()


def delete_link(code):
    conn = get_db()
    try:
        with conn:
            cursor = conn.execute("DELETE FROM urls WHERE code = ?", (code,))
            return cursor.rowcount > 0
    finally:
        conn.close()


app = Flask(__name__, template_folder=str(PROJECT_DIR))
init_db()


@app.route("/", methods=["GET"])
def index():
    links = get_all_links()
    total_links, total_clicks = get_stats()
    return render_template("index.html", links=links, total_links=total_links, total_clicks=total_clicks)


@app.route("/api/shorten", methods=["POST"])
def api_shorten():
    data = request.get_json(silent=True) or request.form
    url = data.get("url", "")
    custom_code = data.get("custom_code", "").strip() or None

    try:
        code = shorten_url(url, custom_code)
        short_url = f"{request.host_url}{code}"
        return jsonify({"success": True, "code": code, "short_url": short_url})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/stats", methods=["GET"])
def api_stats():
    total_links, total_clicks = get_stats()
    links = get_all_links()
    return jsonify({"total_links": total_links, "total_clicks": total_clicks, "links": links})


@app.route("/api/delete/<code>", methods=["DELETE"])
def api_delete(code):
    success = delete_link(code)
    if success:
        return jsonify({"success": True, "message": f"Link /{code} deleted."})
    return jsonify({"success": False, "error": "Link not found."}), 404


@app.get("/<code>")
def resolve(code):
    # Ignore favicon requests
    if code == "favicon.ico":
        return "", 444

    original_url = resolve_and_track_code(code)
    if original_url:
        return redirect(original_url, code=302)
    
    total_links, total_clicks = get_stats()
    return render_template("index.html", links=get_all_links(), total_links=total_links, total_clicks=total_clicks, error=f"No link found for /{code}"), 404


def main():
    print("Starting SwiftLink URL Shortener at http://127.0.0.1:5002 ...")
    threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:5002")).start()
    app.run(port=5002, debug=False)


if __name__ == "__main__":
    main()
