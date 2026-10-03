from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Clientalio Lead Platform"
    api_prefix: str = "/api"
    data_dir: str = Field(default="./data")
    database_url: str = Field(default="sqlite:///./clientalio.db", env="DATABASE_URL")
    request_timeout: int = 15
    max_search_results: int = 500
    search_rate_limit_delay: float = 1.0
    search_max_retries: int = 3
    search_retry_backoff: float = 2.0
    serper_api_key: str | None = Field(default=None, env="SERPER_API_KEY")
    brave_search_api_key: str | None = Field(default=None, env="BRAVE_SEARCH_API_KEY")
    serpapi_api_key: str | None = Field(default=None, env="SERPAPI_API_KEY")
    google_maps_api_key: str | None = Field(default=None, env="GOOGLE_MAPS_API_KEY")
    user_agent: str = Field(default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    max_crawl_retries: int = 2
    batch_workers: int = 8
    # False keeps the browser window visible while scraping/searching.
    headless: bool = Field(default=False, env="HEADLESS")
    # Slow down Playwright actions so a visible run is easy to follow.
    browser_slow_mo_ms: int = Field(default=100, env="BROWSER_SLOW_MS")

    # --- Anti-captcha / rate limiting -------------------------------------
    # Persistent Chromium profile keeps cookies so Google trusts us more.
    browser_profile_dir: str = Field(default="data/browser_profile", env="BROWSER_PROFILE_DIR")
    # Seconds to wait for a human to solve a captcha (visible runs only).
    captcha_wait_seconds: int = Field(default=180, env="CAPTCHA_WAIT_SECONDS")
    # Base pause between Google requests; a random extra is added on top.
    browser_request_delay: float = Field(default=3.0, env="BROWSER_REQUEST_DELAY")
    # Stable UA. Leave empty to use the built-in default; do NOT rotate per query.
    browser_user_agent: str = Field(default="", env="BROWSER_USER_AGENT")
    # Back off this long after a captcha in headless runs.
    captcha_backoff_seconds: int = Field(default=600, env="CAPTCHA_BACKOFF_SECONDS")

    # Product whose leads CSV is read/written: clientalio or dropproof.
    active_product: str = Field(default="clientalio", env="ACTIVE_PRODUCT")

    # Remote Lead Capture API (POST {lead_api_base_url}/api/v1/Lead/LeadCapture)
    lead_api_base_url: str = Field(
        default="https://apiclientalio.azurewebsites.net", env="LEAD_API_BASE_URL"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Product registry: keyword CSV, leads CSV, and the name sent to the Lead API.
PRODUCTS = {
    "clientalio": {
        "key": "clientalio",
        "name": "Clientalio",
        "leads_file": "clientalio_leads.csv",
        "keywords_file": "clientalio_6000_search_keywords.csv",
    },
    "dropproof": {
        "key": "dropproof",
        "name": "Dropproof",
        "leads_file": "dropproof_leads.csv",
        "keywords_file": "dropproof_6000_search_keywords.csv",
    },
}

settings = Settings()
