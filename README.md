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

## Push leads to the Lead Capture API

`push_leads_to_api.py` posts each row of `data/leads.csv` to
`POST {base_url}/api/v1/Lead/LeadCapture`, one lead per request.

Targets (pass one or more to `--target`):

| Name | Base URL |
|---|---|
| `deployed` | `https://apiclientalio.azurewebsites.net` (default) |
| `local` | `http://localhost:5023` — local dev, plain HTTP |
| `local-https` | `https://localhost:7293` — local dev cert, must be trusted |

```bash
python push_leads_to_api.py --dry-run                        # preview against deployed
python push_leads_to_api.py --target local --limit 20         # send to local dev
python push_leads_to_api.py --target deployed local --delay 1.5 --resume
python push_leads_to_api.py --target https://api.example.com  # any other URL
```

Results are appended per target — `data/lead_push_results_<target>.csv` — so local
and deployed runs stay independent. Each run first probes the API root and aborts
that target if it is unreachable. The endpoint returns HTTP 200 even for business
failures, so the script branches on the `success` field of the response envelope
rather than on the status code.

Caveat: the currently deployed build predates the newer payload fields, and
ASP.NET Core drops unknown JSON properties silently — enrichment fields such as
`companyName` will be accepted but not persisted until the API is redeployed and
`DBScript/MarketingLead.sql` is applied.

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

## Run the script
- .\.venv\Scripts\python.exe run_search_csv.py 
