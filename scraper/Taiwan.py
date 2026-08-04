#!/usr/bin/env python3
"""
Taiwan DOT Traffic Camera Scraper
==================================
Downloads real-time live traffic camera locations and image URLs from the
official keyless THB (Provincial Highways) and Freeway Bureau API endpoints,
and saves them into the SQLite database (taiwan_cctv.db).
Bypasses legacy SSL verification issues.
"""

import os
import json
import urllib.request
import ssl
import sqlite3
import datetime
import re

THB_URL = "https://thbapp.thb.gov.tw/services/cctv/thb"
FREEWAY_URL = "https://thbapp.thb.gov.tw/services/cctv/freeway"

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cctv")
DB_NAME = "taiwan_cctv.db"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Create an unverified SSL context for legacy certificates
SSL_CONTEXT = ssl._create_unverified_context()

def init_db(db_path):
    """Initializes the SQLite database with the standard cctv table."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cctv (
            device_id TEXT PRIMARY KEY,
            description TEXT,
            latitude REAL,
            longitude REAL,
            image_url TEXT,
            video_url TEXT,
            region TEXT,
            route TEXT,
            last_updated TEXT
        )
    """)
    conn.commit()
    return conn

def extract_route_taiwan(stakenumber, is_freeway):
    """Parses route/road names from Taiwan's stake number description."""
    if is_freeway:
        match = re.search(r'(國道?\d+號?架?|台\d+線?[甲乙丙丁]?)', stakenumber)
        if match:
            return match.group(1).strip()
        return "National Freeway"
    else:
        match = re.search(r'(台\d+線?[甲乙丙丁]?|縣\d+線?)', stakenumber)
        if match:
            return match.group(1).strip()
        return "Provincial Highway"

def fetch_json(url):
    """Fetches JSON from the target URL using urllib with a custom User-Agent and unverified SSL context."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}")
        return []

def scrape_and_save(db_path):
    print("="*60)
    print("SYNCING TAIWAN DOT TRAFFIC CAMERAS")
    print("="*60)

    # 1. Fetch Provincial Highway Cameras
    print(f"Fetching Provincial Highway cameras from:\n  {THB_URL}")
    thb_cams = fetch_json(THB_URL)
    print(f"Received {len(thb_cams)} provincial highway cameras.")

    # 2. Fetch National Freeway Cameras
    print(f"\nFetching National Freeway cameras from:\n  {FREEWAY_URL}")
    fwy_cams = fetch_json(FREEWAY_URL)
    print(f"Received {len(fwy_cams)} national freeway cameras.")

    all_cams = []
    for c in thb_cams:
        c["_is_freeway"] = False
        all_cams.append(c)
    for c in fwy_cams:
        c["_is_freeway"] = True
        all_cams.append(c)

    if not all_cams:
        print("[WARNING] No camera records found from either endpoint.")
        return

    # Open database connection
    conn = init_db(db_path)
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    saved_count = 0
    for cam in all_cams:
        cam_id = cam.get("id")
        gisx = cam.get("gisx")
        gisy = cam.get("gisy")
        html_url = cam.get("html")
        stakenumber = cam.get("stakenumber", "")

        if not cam_id or not gisx or not gisy or not html_url:
            continue

        try:
            lng = float(gisx)
            lat = float(gisy)
        except ValueError:
            continue

        # Determine type prefix
        prefix = "TWN-FWY" if cam["_is_freeway"] else "TWN-THB"
        device_id = f"{prefix}-{cam_id}"
        
        description = f"{stakenumber} (Taiwan DOT Camera)"
        region = "Taiwan Freeway" if cam["_is_freeway"] else "Taiwan Highway"
        route = extract_route_taiwan(stakenumber, cam["_is_freeway"])

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO cctv 
                (device_id, description, latitude, longitude, image_url, video_url, region, route, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (device_id, description, lat, lng, html_url, None, region, route, timestamp))
            saved_count += 1
        except Exception as se:
            print(f"[ERROR] Saving camera {device_id}: {se}")

    conn.commit()
    conn.close()
    print(f"\n[SUCCESS] Saved {saved_count} Taiwan DOT cameras into: {db_path}")
    print("="*60)

def main():
    db_path = os.path.join(DB_DIR, DB_NAME)
    scrape_and_save(db_path)

if __name__ == "__main__":
    main()
