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
- `data/clientalio_leads.csv` — leads scraped for the Clientalio product
- `data/dropproof_leads.csv` — leads scraped for the Dropproof product
- `data/crawl_log.csv`
- `data/failed_sites.csv`

Each product has its own leads CSV, so the two keyword sets never mix. The product
is chosen once at startup and drives both the file written and the `productName`
sent to the Lead Capture API.

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

## Avoiding Google captcha

Google flags the scraper when it sees automation, so the browser is now shared
rather than relaunched per query:

- **One persistent Chromium profile** (`data/browser_profile`) keeps cookies and
  the consent choice across keywords *and* across runs.
- **One stable user agent**, instead of rotating it on every request.
- **Randomised pacing** — `BROWSER_REQUEST_DELAY` (default 3s) plus jitter,
  doubled between keywords.
- **Captcha detection.** In a visible run the browser stops and waits up to
  `CAPTCHA_WAIT_SECONDS` (default 180) for you to click the checkbox, then
  continues on its own. Headless runs skip that lead instead of hammering.

Website lookups during enrichment use **DuckDuckGo's HTML endpoint first**
(plain HTTP, no browser page, essentially no captcha), falling back to Google
only when it returns nothing. Set `BROWSER_REQUEST_DELAY=6` if captchas persist.

Run `python test_search_live.py` to see live search output.

Offline checks (no network, no browser):

| Script | Covers |
|---|---|
| `test_enrichment.py` | enrichment chain: card → website → snippets → social |
| `test_lead_save.py` | repository save/update round-trip into the CSV |
| `test_search_pipeline.py` | full `search_and_save` flow, including no-website cards |

## Lead enrichment chain

A Google Maps card rarely carries a full lead, and a business with no website was
previously discarded outright. `backend/services/enrichment_service.py` now fills
gaps progressively, stopping as soon as there is enough to work with:

1. **Card** — whatever Maps gave us (name, phone, address, email if listed).
2. **Website** — searched on Google when the card has none, skipping directories
   and social profiles; the company's own domain is preferred.
3. **Crawl** — homepage (hero + footer) plus contact/about/team pages.
4. **Snippets** — email/phone pulled from Google's own result text.
5. **Social** — LinkedIn / WhatsApp profile URL when no website exists anywhere.

Every lead records where each field came from in its `Notes`, e.g.
`Discovery: Maps card, Website found via Google, Website crawl`. Leads with fewer
than two of email/phone/website are flagged unusable and not saved.

Run `python test_enrichment.py` to check the chain offline (no network).

## Push leads to the Lead Capture API

`push_leads_to_api.py` posts each row of the selected product's leads CSV to
`POST {base_url}/api/v1/Lead/LeadCapture`, one lead per request. It asks for the
product too, so the file and the `productName` always match.

| Product | Leads file | `productName` sent |
|---|---|---|
| 1) Clientalio | `data/clientalio_leads.csv` | `Clientalio` |
| 2) Dropproof | `data/dropproof_leads.csv` | `Dropproof` |

```bash
python push_leads_to_api.py --dry-run                        # preview, choose product
python push_leads_to_api.py --product 1 --target local       # push Clientalio to local
python push_leads_to_api.py --product dropproof --resume     # push Dropproof, skip sent
```

Targets (pass one or more to `--target`):

| Name | Base URL |
|---|---|
| `auto` *(default)* | Picks `local` if it's running, otherwise `deployed` |
| `deployed` | `https://apiclientalio.azurewebsites.net` |
| `local` | `http://localhost:5023` — local dev, plain HTTP |
| `local-https` | `https://localhost:7293` — local dev cert, must be trusted |

With no `--target`, the script probes each backend and prints which one it chose:

```
Detecting backend...
  local        is up -> using it (http://localhost:5023)
```

An explicit `--target` or `--base-url` skips detection entirely and is used
verbatim — useful when you want to force production.

```bash
python push_leads_to_api.py --dry-run                        # preview against deployed
python push_leads_to_api.py --product 1 --target local       # send to local dev
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



```bash
cd /Users/shashwatsaxena/Documents/scrapingclientalio
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 run_search_csv.py
```

Then: `1` = Clientalio or `2` = Dropproof, then enter how many keywords. Browser windows open visibly.

**Use that full path.** Plain `python3` is your Anaconda build and is missing `playwright`, `email_validator` and `selenium` — it crashes on import. Cleaner fix, once:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python run_search_csv.py
```

**Variants**

| Command | Effect |
|---|---|
| `python run_search_csv.py` | Menu, visible browser |
| `python run_search_csv.py 1` | Clientalio, no menu |
| `python run_search_csv.py dropproof` | Dropproof, no menu |
| `HEADLESS=true python run_search_csv.py` | No browser window |
| `BROWSER_SLOW_MS=1000 python run_search_csv.py` | Slow, easier to watch |

**Start small.** Answer `1` or `2`, then type `5` at the keyword-count prompt. That exercises the whole new chain — Maps cards, the Google lookup for website-less cards, the crawl, and the `Discovery: ...` note in `data/clientalio_leads.csv`. I'd check that before letting it run hundreds.

Then push:
```bash
python push_leads_to_api.py --product 1 --dry-run --limit 5 # preview
python push_leads_to_api.py --product 1                      # send
```

Honest caveat: I've verified the code compiles, imports, and passes offline tests, but I have **not** run the scraper end-to-end against live Google — that would burn search traffic and write real rows. The Google SERP parser in particular is the part most likely to need a tweak once you see real results. Stop with `Ctrl+C`; progress saves and the next run offers to resume.

.venv/bin/python run_search_csv.py

.venv/bin/python run_search_csv.py clientalio --push
.venv/bin/python push_leads_to_api.py --product clientalio --limit 5