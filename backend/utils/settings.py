from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Clientalio Lead Platform"
    api_prefix: str = "/api"
    data_dir: str = Field(default="./data")
    database_url: str = Field(default="sqlite:///./clientalio.db", env="DATABASE_URL")
    request_timeout: int = 15
    max_search_results: int = 500
    user_agent: str = Field(default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    max_crawl_retries: int = 2
    batch_workers: int = 8

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
