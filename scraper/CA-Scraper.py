#!/usr/bin/env python3
"""
California DOT Traffic Camera Database Saver
--------------------------------------------
Downloads the latest Caltrans Closed Circuit Television (CCTV) GeoJSON feed
and saves all 2,900+ active California highway cameras into the SQLite database
file (california_cctv.db) using the standard unified schema.

Usage:
  python3 scrapper.py
"""

import os
import urllib.request
import json
import sqlite3
import datetime
import ssl

GEOJSON_URL = "https://opendata.arcgis.com/datasets/450df5bed93c4558a7264b7ef64187e6_0.geojson"
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cctv")
DB_NAME = "california_cctv.db"
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

def sync_california(db_path):
    print("="*60)
    print("SYNCING LIVE CALIFORNIA (CALTRANS) HIGHWAY CAMERAS")
    print("="*60)
    print(f"Downloading latest GeoJSON from:\n  {GEOJSON_URL}\n")
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    req = urllib.request.Request(GEOJSON_URL, headers={"User-Agent": USER_AGENT})
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=60) as response:
            raw_data = response.read().decode("utf-8")
        
        data = json.loads(raw_data)
        features = data.get("features", [])
        
        if not features:
            print("[ERROR] No cameras found in the GeoJSON response.")
            return
            
        print(f"Successfully retrieved {len(features)} features. Saving to database...")
        
        conn = init_db(db_path)
        cursor = conn.cursor()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        saved_count = 0
        for feat in features:
            props = feat.get("properties", {})
            geom = feat.get("geometry", {})
            
            # Skip features without geometry
            if not geom or geom.get("type") != "Point" or not geom.get("coordinates"):
                continue
                
            coords = geom["coordinates"]
            lng, lat = coords[0], coords[1]
            
            # Skip if invalid coordinates
            if not lat or not lng:
                continue
                
            device_id = props.get("OBJECTID") or props.get("index_")
            if not device_id:
                continue
                
            description = props.get("locationName") or "Caltrans Camera"
            image_url = props.get("currentImageURL")
            video_url = props.get("streamingVideoURL")
            
            # Region (District + County)
            district_str = f"Caltrans D{props.get('district')}" if props.get("district") else "Caltrans"
            county_str = props.get("county") or ""
            region = f"{district_str} ({county_str})" if county_str else district_str
            
            route = props.get("route") or ""
            
            cursor.execute("""
                INSERT OR REPLACE INTO cctv 
                (device_id, description, latitude, longitude, image_url, video_url, region, route, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (str(device_id), description, float(lat), float(lng), image_url, video_url, region, route, timestamp))
            saved_count += 1
            
        conn.commit()
        conn.close()
        print(f"\n[SUCCESS] Saved {saved_count} California cameras into: {db_path}")
        print("="*60)
        
    except Exception as e:
        print(f"[ERROR] California Sync failed: {e}")

def main():
    db_path = os.path.join(DB_DIR, DB_NAME)
    sync_california(db_path)

if __name__ == "__main__":
    main()
