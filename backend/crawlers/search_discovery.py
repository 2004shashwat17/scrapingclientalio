import logging
from typing import List
from urllib.parse import parse_qs, urlparse, unquote

import requests
from bs4 import BeautifulSoup

from backend.utils.settings import settings
from backend.crawlers.utils import parse_domain

logger = logging.getLogger("clientalio.search")


class SearchDiscovery:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": settings.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def discover(
        self,
        query: str,
        limit: int = 200,
        country: str | None = None,
        industry: str | None = None,
        providers: list[str] | None = None,
    ) -> List[str]:
        providers = providers or ["duckduckgo", "bing"]
        queries = self.build_search_queries(query, country=country, industry=industry)
        results: list[str] = []
        seen_domains: set[str] = set()

        for search_query in queries:
            if len(results) >= limit:
                break
            for provider in providers:
                if len(results) >= limit:
                    break
                try:
                    page_urls = self.search_provider(search_query, provider)
                except Exception as exc:
                    logger.warning("Search provider %s failed for '%s': %s", provider, search_query, exc)
                    continue

                for url in page_urls:
                    domain = parse_domain(url)
                    if not domain or domain in seen_domains:
                        continue
                    normalized = f"https://{domain}"
                    seen_domains.add(domain)
                    results.append(normalized)
                    if len(results) >= limit:
                        break

        return results[:limit]

    def build_search_queries(self, query: str, country: str | None = None, industry: str | None = None) -> List[str]:
        query = query.strip()
        candidates: list[str] = [query]

        if industry and industry.lower() not in query.lower():
            candidates.append(f"{industry} {query}")
        if country:
            candidates.append(f"{query} {country}")
            candidates.append(f"{query} in {country}")
            if industry:
                candidates.append(f"best {industry} agencies in {country}")
                candidates.append(f"top {industry} service providers in {country}")
        if "best" not in query.lower():
            candidates.append(f"best {query}")
        if "top" not in query.lower():
            candidates.append(f"top {query}")
        if industry and "agency" not in query.lower() and "firm" not in query.lower():
            candidates.append(f"{industry} agency {country or ''}".strip())

        unique_queries: list[str] = []
        for item in candidates:
            normalized = " ".join(item.split())
            if normalized and normalized not in unique_queries:
                unique_queries.append(normalized)
        return unique_queries

    def search_provider(self, query: str, provider: str) -> List[str]:
        if provider == "duckduckgo":
            return self.search_duckduckgo(query)
        if provider == "bing":
            return self.search_bing(query)
        raise ValueError(f"Unsupported search provider: {provider}")

    def search_duckduckgo(self, query: str) -> List[str]:
        response = self.session.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            timeout=settings.request_timeout,
        )
        response.raise_for_status()
        return self.parse_duckduckgo_results(response.text)

    def search_bing(self, query: str) -> List[str]:
        response = self.session.get(
            "https://www.bing.com/search",
            params={"q": query},
            timeout=settings.request_timeout,
        )
        response.raise_for_status()
        return self.parse_bing_results(response.text)

    def parse_duckduckgo_results(self, html: str) -> List[str]:
        soup = BeautifulSoup(html, "lxml")
        links: list[str] = []
        for item in soup.select("a.result__a"):
            href = item.get("href")
            if not href:
                continue
            if href.startswith("//duckduckgo.com/l/?uddg=") or href.startswith("/l/?uddg="):
                query = urlparse(href).query
                params = parse_qs(query)
                redirect = params.get("uddg")
                if redirect:
                    links.append(unquote(redirect[0]))
                    continue
            links.append(href)
        return links

    def parse_bing_results(self, html: str) -> List[str]:
        soup = BeautifulSoup(html, "lxml")
        links: list[str] = []
        for anchor in soup.select("li.b_algo h2 a"):
            href = anchor.get("href")
            if href:
                links.append(href)
        return links
