# Clientalio Lead Generation & Website Enrichment Platform

A production-ready lead discovery, crawling, enrichment, scoring, and export platform for agency and service business prospecting.

## Architecture

- `backend/`
  - `api/` FastAPI application and routers
  - `services/` business logic and scoring
  - `repositories/` CSV persistence logic
  - `schemas/` request and response schemas
  - `crawlers/` discovery and website enrichment logic
  - `storage/` CSV file storage for leads and logs
  - `utils/` settings, logging, and helper utilities
- `frontend/` simple single-page UI for search, lead list, detail view, and export

## Storage

This MVP stores leads and crawl logs in CSV files for fast setup and Excel-native exports:
- `data/leads.csv`
- `data/crawl_log.csv`
- `data/failed_sites.csv`

## Setup

1. Create a Python 3.12 environment
2. Install dependencies: `pip install -r requirements.txt`
3. No database is required for this MVP. Data is stored directly in CSV files under `data/`.

4. Run development server:
   `uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload`

## API Endpoints

- `POST /search`
- `POST /crawl`
- `GET /leads`
- `GET /lead/{id}`
- `GET /export/csv`
- `GET /export/excel`

## Notes

- Uses requests + BeautifulSoup for standard crawling
- Selenium is available only when JavaScript rendering is needed
- Duplicate detection is based on domain, email, and company name
- Error handling includes retries, timeouts, and crawl logging

cd /Users/shashwatsaxena/Desktop/SCRAPINGCLIENTALIO
python3 process_leads.py

cd /Users/shashwatsaxena/Desktop/SCRAPINGCLIENTALIO
python3 generate_email_list.py  # generates email_list.csv

python3 run_search_csv.py                         

