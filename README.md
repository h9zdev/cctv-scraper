# cctv-scraper



![Banner](https://raw.githubusercontent.com/h9zdev/cctv-scraper/main/SocioSential.png)

![Python](https://img.shields.io/badge/python-3.10%2B-00FFD1?style=flat-square&logo=python&logoColor=black)
![Flask](https://img.shields.io/badge/flask-viewer-00FFD1?style=flat-square&logo=flask&logoColor=black)
![Status](https://img.shields.io/badge/status-active-00FFD1?style=flat-square)
![OSINT](https://img.shields.io/badge/purpose-OSINT%20%2F%20research-9D00FF?style=flat-square)
[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-9D00FF.svg?style=flat-square)](https://creativecommons.org/licenses/by-nc/4.0/)

Scrapes publicly available CCTV camera metadata from DOT (Department of Transportation) and other open sources, then stores it in a structured database for research, analysis, and indexing.
## Features

- Scrapes public CCTV metadata (camera ID, location, coordinates, feed URL, status) from open DOT/state traffic feeds and other public sources
- Normalizes and stores results in a structured local database
- Modular scraper design (`scraper/`) for adding new sources/endpoints
- Built-in Flask viewer with map + searchable table for browsing indexed data
- Built for OSINT/research indexing, not live surveillance capture

## Repo structure

```
cctv-scraper/
├── database/     # Indexed camera data (output of scraper runs)
├── scraper/      # Location-based scraper scripts (one per source/region)
├── viewer/       # Flask app for browsing the indexed database
├── .gitignore
└── README.md
```

- **`database/`** — holds the indexed CCTV metadata scraped so far (camera IDs, coordinates, feed URLs, source, status). This is the output/index, not code.
- **`scraper/`** — the actual scrapers, organized by location/source. There is no single `main.py` entrypoint — each script targets a specific DOT/state/region source.
- **`viewer/`** — standalone Flask app that reads directly from `database/*.db` and renders a map + filterable table. See [Viewer](#viewer) below.

## Requirements

- Python 3.10+
- pip

## Installation

```bash
git clone https://github.com/h9zdev/cctv-scraper.git
cd cctv-scraper
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install requests beautifulsoup4 sqlalchemy pandas
```

## Usage

Run a scraper script for the location/source you want data from:

```bash
python3 scraper/<script-name>.py
```

Example:

```bash
python3 scraper/nyc-scraper.py
python3 scraper/CA-Scraper.py
python3 scraper/TX-scrapper.py
python3 scraper/FL-IA-Scarper.py
```

Results get written/indexed into `database/`.

## Viewer

A Flask-based tactical dashboard for browsing indexed camera data — map view, per-source stats, search, and pagination — built directly on top of the `database/*.db` files, no separate ingestion step required.

```bash
pip install flask
cd viewer
python3 app.py
```

Then open `http://localhost:5050`.

- Sidebar switches between indexed sources (`GLOBAL`, `CALIFORNIA`, `TEXAS`, `IOWA`, `NYC`)
- Live Leaflet map plots every camera with coordinates for the selected source
- Search filters by name/region, results are paginated server-side
- Each row links out to the camera's media/feed URL where available

The viewer is read-only — it never triggers a scrape, it just visualizes what's already in `database/`.

## Contributing a new location

Want to add a source/region that isn't covered yet:

1. Fork the repo
2. Add a new script under `scraper/` for that location (follow the pattern of an existing script in that folder)
3. Point it at the public DOT/traffic-cam source for that place, and have it write its output into `database/`
4. Open a PR

## Notes

- Only scrapes **publicly available** metadata exposed by DOT/state traffic portals and similar open sources.
- Intended for research, indexing, and OSINT analysis. Respect the target site's ToS and rate limits.

## License

Licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) — Attribution, NonCommercial. See [LICENSE.md](LICENSE.md) for full terms.

## Author

[h9zdev](https://github.com/h9zdev)
