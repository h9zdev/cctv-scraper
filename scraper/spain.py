#!/usr/bin/env python3
"""
Spain DOT (Ayuntamiento de Madrid) Traffic Camera Scraper
========================================================
Downloads real-time live traffic camera locations and image URLs from the
official Madrid Open Data KML feed, parses the coordinates and image sources,
and saves them into the SQLite database (spain_cctv.db).
"""

import os
import urllib.request
import xml.etree.ElementTree as ET
import sqlite3
import datetime
import re

KML_URL = "http://datos.madrid.es/egob/catalogo/202088-0-trafico-camaras.kml"
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cctv")
DB_NAME = "spain_cctv.db"
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

def parse_kml_and_save(db_path):
    print("="*60)
    print("SYNCING SPAIN DOT TRAFFIC CAMERAS (Madrid)")
    print("="*60)
    print(f"Downloading KML from:\n  {KML_URL}\n")

    req = urllib.request.Request(KML_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw_data = response.read()
    except Exception as e:
        print(f"[ERROR] Failed to download KML feed: {e}")
        return

    try:
        root = ET.fromstring(raw_data)
    except Exception as e:
        print(f"[ERROR] Failed to parse KML XML: {e}")
        return

    # Find all Placemark elements using namespace wildcard
    placemarks = root.findall('.//{*}Placemark')
    print(f"Found {len(placemarks)} camera nodes in KML.")

    if not placemarks:
        print("[WARNING] No placemarks found in the KML.")
        return

    # Open database connection
    conn = init_db(db_path)
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    saved_count = 0
    for idx, pm in enumerate(placemarks):
        # Extract coordinates
        coord_elem = pm.find('.//{*}coordinates')
        if coord_elem is None or not coord_elem.text:
            continue

        coords_str = coord_elem.text.strip()
        coords_parts = coords_str.split(',')
        if len(coords_parts) < 2:
            continue

        try:
            lng = float(coords_parts[0])
            lat = float(coords_parts[1])
        except ValueError:
            continue

        # Extract name/number
        number = None
        name = f"Camera {idx}"
        
        for data in pm.findall('.//{*}Data'):
            data_name = data.get("name")
            val_elem = data.find('{*}Value')
            if val_elem is not None and val_elem.text:
                if data_name == "Numero":
                    number = val_elem.text.strip()
                elif data_name == "Nombre":
                    name = val_elem.text.strip()

        if not number:
            number = str(idx)

        # Extract image URL from description
        desc_elem = pm.find('.//{*}description')
        image_url = None
        if desc_elem is not None and desc_elem.text:
            desc_text = desc_elem.text
            # Look for src=http... or src=https...
            img_match = re.search(r'src=["\']?(https?://[^\s"\'>]+)["\']?', desc_text, re.IGNORECASE)
            if img_match:
                image_url = img_match.group(1).strip()

        # Fallback if image URL is not found in description
        if not image_url and number:
            # Build URL based on common pattern
            image_url = f"https://informo.madrid.es/cameras/Camara{number.zfill(5)}.jpg"

        device_id = f"ESP-MAD-{number}"
        description = f"{name} (Madrid DOT Camera)"
        region = "Madrid, Spain"
        
        # Route parsing
        route = "M-30" if "M-30" in name or "M30" in name else "Calle / Plaza"
        if route == "Calle / Plaza":
            # Extract main street if possible
            hwy_match = re.search(r'([A-Za-z0-9\s\-]+(Calle|Plaza|Paseo|Avda|Avenida|C/|Gran Vía|Autovía|A\-[0-9]+|M\-[0-9]+))', name, re.IGNORECASE)
            if hwy_match:
                route = hwy_match.group(1).strip()
            else:
                route = name.split(' - ')[0].split(' / ')[0].strip()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO cctv 
                (device_id, description, latitude, longitude, image_url, video_url, region, route, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (device_id, description, lat, lng, image_url, None, region, route, timestamp))
            saved_count += 1
        except Exception as se:
            print(f"[ERROR] Saving camera {device_id}: {se}")

    conn.commit()
    conn.close()
    print(f"\n[SUCCESS] Saved {saved_count} Spain DOT cameras into: {db_path}")
    print("="*60)

def main():
    db_path = os.path.join(DB_DIR, DB_NAME)
    parse_kml_and_save(db_path)

if __name__ == "__main__":
    main()
