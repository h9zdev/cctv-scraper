# cctv-scraper

Scrapes publicly available CCTV camera metadata from DOT (Department of Transportation) and other open sources, then stores it in a structured database for research, analysis, and indexing.

![Banner](https://raw.githubusercontent.com/h9zdev/cctv-scraper/main/SocioSential.png)

## Features

- Scrapes public CCTV metadata (camera ID, location, coordinates, feed URL, status) from open DOT/state traffic feeds and other public sources
- Normalizes and stores results in a structured local database
- Modular scraper design (`scraper/`) for adding new sources/endpoints
- Built for OSINT/research indexing, not live surveillance capture

## Repo structure

```
cctv-scraper/
├── database/     # Indexed camera data (output of scraper runs)
├── scraper/      # Location-based scraper scripts (one per source/region)
├── .gitignore
└── README.md
```

- **`database/`** — holds the indexed CCTV metadata scraped so far (camera IDs, coordinates, feed URLs, source, status). This is the output/index, not code.
- **`scraper/`** — the actual scrapers, organized by location/source. There is no single `main.py` entrypoint — each script targets a specific DOT/state/region source.

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
python3 scraper/<location>.py
```

Example:

```bash
python3 scraper/newyork.py
python3 scraper/texas.py
```

Results get written/indexed into `database/`.

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

Specify a license (MIT, GPL-3.0, etc.) — none currently set in the repo.

## Author

[h9zdev](https://github.com/h9zdev)
