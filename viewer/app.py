#!/usr/bin/env python3
"""
CCTV-SCRAPER // TACTICAL VIEWER
Flask viewer for the cctv-scraper SQLite databases.
"""
import sqlite3
from pathlib import Path
from flask import Flask, render_template, request, jsonify, g

BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR.parent / "database"

# Each key = state, value = (db filename, table, column map -> normalized fields)
SOURCES = {
    "GLOBAL":     {"file": "cctv.db",            "table": "cameras", "cols": {
        "id": "id", "name": "source_agency", "lat": "lat", "lon": "lon",
        "extra": "direction_facing", "media": "media_url",
        "region": "source_agency", "updated": "last_updated",
    }},
    "CALIFORNIA": {"file": "california_cctv.db",  "table": "cctv", "cols": {
        "id": "device_id", "name": "description", "lat": "latitude", "lon": "longitude",
        "extra": "route", "media": "image_url",
        "region": "region", "updated": "last_updated",
    }},
    "TEXAS":      {"file": "texas_cctv.db",       "table": "cctv", "cols": {
        "id": "device_id", "name": "description", "lat": "latitude", "lon": "longitude",
        "extra": "route", "media": "image_url",
        "region": "region", "updated": "last_updated",
    }},
    "IOWA":       {"file": "iowa_cctv.db",        "table": "cctv", "cols": {
        "id": "device_id", "name": "description", "lat": "latitude", "lon": "longitude",
        "extra": "route", "media": "image_url",
        "region": "region", "updated": "last_updated",
    }},
    "NYC":        {"file": "nyc_cctv.db",         "table": "cctv", "cols": {
        "id": "device_id", "name": "description", "lat": "latitude", "lon": "longitude",
        "extra": "route", "media": "image_url",
        "region": "region", "updated": "last_updated",
    }},
}

app = Flask(__name__)


def get_conn(db_file):
    path = DB_DIR / db_file
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def normalize_rows(rows, cols):
    out = []
    for r in rows:
        out.append({
            "id": r[cols["id"]],
            "name": r[cols["name"]] or "UNKNOWN",
            "lat": r[cols["lat"]],
            "lon": r[cols["lon"]],
            "extra": r[cols["extra"]] or "",
            "media": r[cols["media"]] or "",
            "region": r[cols["region"]] or "",
            "updated": str(r[cols["updated"]] or ""),
        })
    return out


@app.route("/")
def index():
    return render_template("index.html", sources=list(SOURCES.keys()))


@app.route("/api/stats")
def api_stats():
    stats = {}
    for state, cfg in SOURCES.items():
        try:
            conn = get_conn(cfg["file"])
            count = conn.execute(f"SELECT COUNT(*) FROM {cfg['table']}").fetchone()[0]
            conn.close()
            stats[state] = count
        except Exception:
            stats[state] = 0
    return jsonify(stats)


@app.route("/api/cameras")
def api_cameras():
    state = request.args.get("state", "GLOBAL").upper()
    search = request.args.get("search", "").strip()
    page = max(int(request.args.get("page", 1)), 1)
    per_page = min(int(request.args.get("per_page", 50)), 500)

    if state not in SOURCES:
        return jsonify({"error": "unknown state", "rows": [], "total": 0}), 404

    cfg = SOURCES[state]
    cols = cfg["cols"]
    conn = get_conn(cfg["file"])

    where = ""
    params = []
    if search:
        where = f" WHERE {cols['name']} LIKE ? OR {cols['region']} LIKE ?"
        like = f"%{search}%"
        params = [like, like]

    total = conn.execute(f"SELECT COUNT(*) FROM {cfg['table']}{where}", params).fetchone()[0]

    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT * FROM {cfg['table']}{where} LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()
    conn.close()

    return jsonify({
        "rows": normalize_rows(rows, cols),
        "total": total,
        "page": page,
        "per_page": per_page,
        "state": state,
    })


@app.route("/api/cameras/map")
def api_cameras_map():
    """Lightweight endpoint returning ALL geo points for a state (for map plotting)."""
    state = request.args.get("state", "GLOBAL").upper()
    if state not in SOURCES:
        return jsonify([]), 404
    cfg = SOURCES[state]
    cols = cfg["cols"]
    conn = get_conn(cfg["file"])
    rows = conn.execute(
        f"SELECT {cols['id']} as id, {cols['name']} as name, "
        f"{cols['lat']} as lat, {cols['lon']} as lon "
        f"FROM {cfg['table']} WHERE {cols['lat']} IS NOT NULL AND {cols['lon']} IS NOT NULL"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5050)
