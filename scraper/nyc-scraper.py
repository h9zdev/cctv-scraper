#!/usr/bin/env python3
"""
NYC DOT Traffic Camera Scraper & Database Saver
------------------------------------------------
Retrieves all NYC DOT traffic cameras from the NYCTMC webcams API
and saves coordinates + image URLs into a SQLite database (nyc_cctv.db).

The NYCTMC API provides:
  - Camera list:  https://webcams.nyctmc.org/api/cameras
  - Camera image: https://webcams.nyctmc.org/api/cameras/{id}/image

Usage:
  1. Full Sync (Fetch all NYC cameras):
     python3 scrapper.py

  2. Fetch a specific camera by ID:
     python3 scrapper.py 563

  3. Custom output database name:
     python3 scrapper.py --db my_cameras.db

  4. List all boroughs/regions found:
     python3 scrapper.py --list-regions
"""

import sys
import os
import urllib.request
import json
import sqlite3
import datetime
import ssl
import time

# ── Configuration ──────────────────────────────────────────────────────────────
CAMERAS_API   = "https://webcams.nyctmc.org/api/cameras"
IMAGE_BASE    = "https://webcams.nyctmc.org/api/cameras"
DB_DIR        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cctv")
DB_NAME       = "nyc_cctv.db"
USER_AGENT    = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                 "AppleWebKit/537.36 (KHTML, like Gecko) "
                 "Chrome/126.0.0.0 Safari/537.36")

# ── Database ───────────────────────────────────────────────────────────────────
def init_db(db_path):
    """Creates (or opens) the SQLite database with the cctv table."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cctv (
            device_id    TEXT PRIMARY KEY,
            description  TEXT,
            latitude     REAL,
            longitude    REAL,
            image_url    TEXT,
            video_url    TEXT,
            region       TEXT,
            route        TEXT,
            last_updated TEXT
        )
    """)
    conn.commit()
    return conn


# ── HTTP Helper ────────────────────────────────────────────────────────────────
def make_request(url, retries=3, timeout=30):
    """Performs an HTTP GET with retries and returns the decoded response string."""
    # Allow unverified SSL for the NYCTMC endpoint (self-signed cert edge cases)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://webcams.nyctmc.org/",
    }
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except Exception as e:
            print(f"  [RETRY {attempt}/{retries}] {e}")
            if attempt < retries:
                time.sleep(2 * attempt)
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts")


# ── Camera Parsing ─────────────────────────────────────────────────────────────
def parse_cameras(raw_json):
    """
    Parses the NYCTMC JSON response into a flat list of camera dicts.
    
    The API returns a list of camera-group objects, each with a `cameras` array.
    Each camera has: id, name, latitude, longitude, etc.
    """
    data = json.loads(raw_json)
    cameras = []

    # The response can be a list of groups or a flat list of cameras
    items = data if isinstance(data, list) else [data]

    for item in items:
        # Each item may be a camera group with nested cameras
        if "cameras" in item and isinstance(item["cameras"], list):
            for cam in item["cameras"]:
                parsed = _extract_camera(cam, group_name=item.get("name"))
                if parsed:
                    cameras.append(parsed)
        else:
            # Direct camera object
            parsed = _extract_camera(item)
            if parsed:
                cameras.append(parsed)

    return cameras


def _extract_camera(cam, group_name=None):
    """Extracts a standardised camera dict from a raw NYCTMC camera object."""
    cam_id = cam.get("id")
    if cam_id is None:
        return None

    lat = cam.get("latitude") or cam.get("lat")
    lng = cam.get("longitude") or cam.get("lng") or cam.get("lon")
    if lat is None or lng is None:
        return None

    name = cam.get("name") or cam.get("cameraName") or cam.get("title") or f"NYC Camera {cam_id}"
    
    # Build the image URL
    image_url = f"{IMAGE_BASE}/{cam_id}/image"
    
    # Some cameras expose a video/stream URL
    video_url = cam.get("videoUrl") or cam.get("hlsUrl") or cam.get("streamUrl") or None

    # Region / borough
    region = (cam.get("borough")
              or cam.get("region")
              or cam.get("areaName")
              or group_name
              or "NYC")

    # Road / route
    route = cam.get("roadway") or cam.get("road") or cam.get("route") or ""

    return {
        "device_id":   str(cam_id),
        "description": str(name).strip(),
        "latitude":    float(lat),
        "longitude":   float(lng),
        "image_url":   image_url,
        "video_url":   video_url,
        "region":      str(region).strip(),
        "route":       str(route).strip(),
    }


# ── Database Persistence ──────────────────────────────────────────────────────
def save_cameras_to_db(conn, cameras):
    """Upserts a list of camera dicts into the cctv table."""
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    saved = 0
    for cam in cameras:
        cursor.execute("""
            INSERT OR REPLACE INTO cctv
            (device_id, description, latitude, longitude, image_url, video_url, region, route, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cam["device_id"],
            cam["description"],
            cam["latitude"],
            cam["longitude"],
            cam["image_url"],
            cam["video_url"],
            cam["region"],
            cam["route"],
            timestamp,
        ))
        saved += 1
    conn.commit()
    return saved


# ── Commands ──────────────────────────────────────────────────────────────────
def full_sync(db_path):
    """Fetches ALL NYC cameras and saves them to the database."""
    print("=" * 60)
    print("  NYC DOT TRAFFIC CAMERA SCRAPER")
    print("  Target: NYCTMC Webcams API")
    print("=" * 60)
    print(f"\n[1/3] Fetching camera list from {CAMERAS_API} ...")

    try:
        raw = make_request(CAMERAS_API)
    except RuntimeError as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)

    print(f"[2/3] Parsing camera data ...")
    cameras = parse_cameras(raw)

    if not cameras:
        print("[ERROR] No cameras found in the API response.")
        print("        The API may be geo-blocked or temporarily down.")
        sys.exit(1)

    print(f"       Found {len(cameras)} cameras across NYC.")

    # Count by region
    regions = {}
    for c in cameras:
        r = c["region"]
        regions[r] = regions.get(r, 0) + 1
    print("\n       Breakdown by region:")
    for r in sorted(regions.keys()):
        print(f"         {r:<20s}  {regions[r]:>4d} cameras")

    print(f"\n[3/3] Saving to database: {db_path}")
    conn = init_db(db_path)
    saved = save_cameras_to_db(conn, cameras)
    conn.close()

    print(f"\n[SUCCESS] Saved {saved} cameras into {db_path}")
    print(f"          Database size: {os.path.getsize(db_path) / 1024:.1f} KB")
    print("=" * 60)


def fetch_single(db_path, cam_id):
    """Fetches the full camera list but only saves/displays one camera."""
    print(f"Querying NYCTMC API for Camera ID: {cam_id} ...")
    try:
        raw = make_request(CAMERAS_API)
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    cameras = parse_cameras(raw)
    match = [c for c in cameras if str(c["device_id"]) == str(cam_id)]

    if not match:
        print(f"[WARNING] Camera ID {cam_id} not found in NYCTMC database.")
        print(f"          Total cameras available: {len(cameras)}")
        return

    cam = match[0]
    conn = init_db(db_path)
    save_cameras_to_db(conn, [cam])
    conn.close()

    print("\n" + "=" * 50)
    print("CAMERA DETAIL FOUND:")
    print(f"  ID          : {cam['device_id']}")
    print(f"  Description : {cam['description']}")
    print(f"  Coordinates : {cam['latitude']}, {cam['longitude']}")
    print(f"  Snapshot URL: {cam['image_url']}")
    print(f"  Video Stream: {cam['video_url'] or 'N/A'}")
    print(f"  Region      : {cam['region']}")
    print(f"  Route       : {cam['route']}")
    print("=" * 50)
    print(f"[SUCCESS] Updated Camera {cam_id} in database: {db_path}")


def list_regions(db_path):
    """Lists all unique regions from the API without saving."""
    print("Fetching camera list to enumerate regions ...")
    try:
        raw = make_request(CAMERAS_API)
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    cameras = parse_cameras(raw)
    regions = {}
    for c in cameras:
        r = c["region"]
        regions[r] = regions.get(r, 0) + 1

    print(f"\nFound {len(cameras)} cameras across {len(regions)} regions:\n")
    for r in sorted(regions.keys()):
        print(f"  {r:<25s}  {regions[r]:>4d} cameras")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    db_path = os.path.join(DB_DIR, DB_NAME)

    args = sys.argv[1:]

    # Handle flags
    if "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    if "--list-regions" in args:
        list_regions(db_path)
        sys.exit(0)

    # Custom DB name
    if "--db" in args:
        idx = args.index("--db")
        if idx + 1 < len(args):
            custom_name = args[idx + 1]
            if not custom_name.endswith(".db"):
                custom_name += ".db"
            db_path = os.path.join(DB_DIR, custom_name)
            args = [a for i, a in enumerate(args) if i != idx and i != idx + 1]
        else:
            print("[ERROR] --db requires a database name argument")
            sys.exit(1)

    # Single camera lookup
    remaining = [a for a in args if not a.startswith("--")]
    if remaining:
        try:
            cam_id = remaining[0].strip()
        except Exception:
            print(f"[ERROR] Invalid camera ID: '{remaining[0]}'")
            print("        Please pass a valid camera ID")
            sys.exit(1)
        fetch_single(db_path, cam_id)
    else:
        full_sync(db_path)


if __name__ == "__main__":
    main()
