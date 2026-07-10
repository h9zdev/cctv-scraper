#!/usr/bin/env python3
"""
Traffic Camera Scraper & Database Saver (Iowa, New York, Florida)
-----------------------------------------------------------------
Fetches coordinates, descriptions, and media feeds for traffic cameras,
saving them in a unified SQLite schema across regional databases:
  - Iowa:      iowa_cctv.db
  - New York:  nyc_cctv.db
  - Florida:   florida_cctv.db

Usage:
  1. Sync a specific region:
     python3 scrapper.py iowa
     python3 scrapper.py nyc
     python3 scrapper.py florida

  2. Sync all regions (default):
     python3 scrapper.py all
"""

import sys
import os
import urllib.request
import json
import sqlite3
import datetime
import ssl
import time

# ── Endpoints & Config ────────────────────────────────────────────────────────
IOWA_API = "https://services.arcgis.com/8lRhdTsQyJpO52F1/ArcGIS/rest/services/Traffic_Cameras_View/FeatureServer/0/query"
NYC_API = "https://webcams.nyctmc.org/api/cameras"
FLORIDA_API = "https://services.arcgis.com/3wFbqsFPLeKqOlIK/arcgis/rest/services/FL511_Traffic_Cameras/FeatureServer/0/query"

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cctv")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ── Unified Schema ─────────────────────────────────────────────────────────────
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

# ── Request Helper ─────────────────────────────────────────────────────────────
def make_request(url, retries=3, timeout=30):
    """Performs HTTP GET with User-Agent header, custom SSL context, and retries."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
    })
    
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as response:
                return response.read().decode("utf-8")
        except Exception as e:
            print(f"  [RETRY {attempt}/{retries}] Error: {e}")
            if attempt < retries:
                time.sleep(2 * attempt)
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts")

# ── Region-Specific Syncs ──────────────────────────────────────────────────────

def sync_iowa(db_path):
    print("\n" + "="*50)
    print("SYNCING IOWA DOT TRAFFIC CAMERAS")
    print("="*50)
    
    query_params = "where=1%3D1&outFields=*&f=json"
    url = f"{IOWA_API}?{query_params}"
    
    try:
        response_text = make_request(url)
        data = json.loads(response_text)
        features = data.get("features", [])
        
        if not features:
            print("[ERROR] No Iowa cameras found in response.")
            return
        
        conn = init_db(db_path)
        cursor = conn.cursor()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        saved_count = 0
        for feat in features:
            attrs = feat.get("attributes", {})
            device_id = attrs.get("device_id")
            if not device_id:
                continue
            
            description = attrs.get("Desc_") or attrs.get("ImageName") or "Iowa DOT Camera"
            latitude = attrs.get("latitude")
            longitude = attrs.get("longitude")
            image_url = attrs.get("ImageURL")
            video_url = attrs.get("VideoURL")
            region = attrs.get("REGION") or "Iowa"
            route = attrs.get("Route") or ""
            
            cursor.execute("""
                INSERT OR REPLACE INTO cctv 
                (device_id, description, latitude, longitude, image_url, video_url, region, route, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (str(device_id), description, latitude, longitude, image_url, video_url, region, route, timestamp))
            saved_count += 1
            
        conn.commit()
        conn.close()
        print(f"[SUCCESS] Saved {saved_count} Iowa cameras into: {db_path}")
        
    except Exception as e:
        print(f"[ERROR] Iowa Sync failed: {e}")


def sync_nyc(db_path):
    print("\n" + "="*50)
    print("SYNCING NEW YORK CITY TRAFFIC CAMERAS")
    print("="*50)
    
    try:
        raw_json = make_request(NYC_API)
        data = json.loads(raw_json)
        
        items = data if isinstance(data, list) else [data]
        cameras = []
        
        def process_cam(cam, parent_name=None):
            cam_id = cam.get("id")
            if not cam_id:
                return
            lat = cam.get("latitude") or cam.get("lat")
            lng = cam.get("longitude") or cam.get("lng") or cam.get("lon")
            name = cam.get("name") or cam.get("cameraName") or cam.get("title") or f"NYC Camera {cam_id}"
            image_url = cam.get("imageUrl") or f"https://webcams.nyctmc.org/api/cameras/{cam_id}/image"
            video_url = cam.get("videoUrl") or cam.get("hlsUrl") or None
            region = cam.get("borough") or cam.get("area") or parent_name or "NYC"
            route = cam.get("roadway") or ""
            
            cameras.append({
                "device_id": str(cam_id),
                "description": str(name).strip(),
                "latitude": float(lat) if lat else None,
                "longitude": float(lng) if lng else None,
                "image_url": image_url,
                "video_url": video_url,
                "region": str(region).strip(),
                "route": str(route).strip()
            })

        for item in items:
            if "cameras" in item and isinstance(item["cameras"], list):
                for cam in item["cameras"]:
                    process_cam(cam, parent_name=item.get("name"))
            else:
                process_cam(item)
                        
        conn = init_db(db_path)
        cursor = conn.cursor()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        saved_count = 0
        for cam in cameras:
            if cam["latitude"] is None or cam["longitude"] is None:
                continue
            cursor.execute("""
                INSERT OR REPLACE INTO cctv 
                (device_id, description, latitude, longitude, image_url, video_url, region, route, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (cam["device_id"], cam["description"], cam["latitude"], cam["longitude"], 
                  cam["image_url"], cam["video_url"], cam["region"], cam["route"], timestamp))
            saved_count += 1
            
        conn.commit()
        conn.close()
        print(f"[SUCCESS] Saved {saved_count} NYC cameras into: {db_path}")
        
    except Exception as e:
        print(f"[ERROR] NYC Sync failed: {e}")



def sync_florida(db_path):
    print("\n" + "="*50)
    print("SYNCING FLORIDA DOT TRAFFIC CAMERAS")
    print("="*50)
    
    conn = init_db(db_path)
    total_saved = 0
    offset = 0
    limit = 1000
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    while True:
        print(f"Fetching Florida cameras {offset} to {offset + limit}...")
        query_params = f"where=1%3D1&outFields=*&resultOffset={offset}&resultRecordCount={limit}&f=json"
        url = f"{FLORIDA_API}?{query_params}"
        
        try:
            response_text = make_request(url)
            data = json.loads(response_text)
            features = data.get("features", [])
            
            if not features:
                break
                
            cursor = conn.cursor()
            saved = 0
            for feat in features:
                attrs = feat.get("attributes", {})
                device_id = attrs.get("ID") or attrs.get("OBJECTID_1")
                if not device_id:
                    continue
                
                description = attrs.get("DESCRIPT") or "Florida DOT Camera"
                latitude = attrs.get("LATITUDE")
                longitude = attrs.get("LONGITUDE")
                image_url = attrs.get("IMAGE")
                video_url = None
                region = attrs.get("COUNTY") or "Florida"
                route = attrs.get("HIGHWAY") or ""
                
                cursor.execute("""
                    INSERT OR REPLACE INTO cctv 
                    (device_id, description, latitude, longitude, image_url, video_url, region, route, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (str(device_id), description, latitude, longitude, image_url, video_url, region, route, timestamp))
                saved += 1
                
            conn.commit()
            total_saved += saved
            
            if len(features) < limit:
                break
                
            offset += len(features)
            time.sleep(0.5)
            
        except Exception as e:
            print(f"[ERROR] Florida Sync failed at offset {offset}: {e}")
            break
            
    conn.close()
    print(f"[SUCCESS] Saved {total_saved} Florida cameras into: {db_path}")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    # Make sure DB directory exists
    os.makedirs(DB_DIR, exist_ok=True)
    
    target = "all"
    if len(sys.argv) > 1:
        target = sys.argv[1].lower()
        
    if target == "iowa":
        sync_iowa(os.path.join(DB_DIR, "iowa_cctv.db"))
    elif target == "nyc" or target == "newyork":
        sync_nyc(os.path.join(DB_DIR, "nyc_cctv.db"))
    elif target == "florida":
        sync_florida(os.path.join(DB_DIR, "florida_cctv.db"))
    elif target == "all":
        sync_iowa(os.path.join(DB_DIR, "iowa_cctv.db"))
        sync_nyc(os.path.join(DB_DIR, "nyc_cctv.db"))
        sync_florida(os.path.join(DB_DIR, "florida_cctv.db"))
    else:
        print(f"[ERROR] Unknown region: '{target}'")
        print("Supported regions: iowa, nyc (or newyork), florida, all")
        sys.exit(1)

if __name__ == "__main__":
    main()
