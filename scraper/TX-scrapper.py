#!/usr/bin/env python3
"""
Texas Traffic Camera Database Saver
-----------------------------------
Retrieves traffic cameras from the Texas (Austin) Open Data Portal
and saves coordinates and snapshot URLs into a SQLite database (texas_cctv.db).

Usage:
  python3 scrapper.py
"""

import os
import urllib.request
import json
import sqlite3
import datetime

AUSTIN_API = "https://data.austintexas.gov/resource/b4k4-adkb.json?$limit=2000"
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cctv")
DB_NAME = "texas_cctv.db"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

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

def sync_texas(db_path):
    print("="*60)
    print("SYNCING TEXAS (AUSTIN) TRAFFIC CAMERAS")
    print("="*60)
    print(f"Downloading latest data from:\n  {AUSTIN_API}\n")
    
    req = urllib.request.Request(AUSTIN_API, headers={"User-Agent": USER_AGENT})
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw_data = response.read().decode("utf-8")
        
        cameras = json.loads(raw_data)
        
        if not cameras:
            print("[ERROR] No cameras found in the API response.")
            return
            
        print(f"Successfully retrieved {len(cameras)} cameras. Saving to database...")
        
        conn = init_db(db_path)
        cursor = conn.cursor()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        saved_count = 0
        for cam in cameras:
            camera_id = cam.get("camera_id")
            if not camera_id:
                continue
                
            location = cam.get("location", {})
            coords = location.get("coordinates")
            if not coords or len(coords) < 2:
                continue
                
            lng, lat = coords[0], coords[1]
            description = cam.get("location_name") or "Texas Traffic Camera"
            image_url = cam.get("screenshot_address")
            video_url = None  # Austin provides still snapshots
            region = "Austin TX"
            route = cam.get("primary_st") or ""
            
            cursor.execute("""
                INSERT OR REPLACE INTO cctv 
                (device_id, description, latitude, longitude, image_url, video_url, region, route, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (f"ATX-{camera_id}", description, float(lat), float(lng), image_url, video_url, region, route, timestamp))
            saved_count += 1
            
        conn.commit()
        conn.close()
        print(f"\n[SUCCESS] Saved {saved_count} Texas cameras into: {db_path}")
        print("="*60)
        
    except Exception as e:
        print(f"[ERROR] Texas Sync failed: {e}")

def main():
    db_path = os.path.join(DB_DIR, DB_NAME)
    sync_texas(db_path)

if __name__ == "__main__":
    main()
