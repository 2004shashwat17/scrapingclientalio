import base64
import json
import logging
import random
import time
from typing import List
from urllib.parse import parse_qs, quote, urlparse, unquote

import requests
from bs4 import BeautifulSoup
from requests import Response
from requests.exceptions import ConnectionError, HTTPError, RequestException, SSLError, Timeout

from backend.utils.settings import settings
from backend.crawlers.utils import parse_domain

logger = logging.getLogger("clientalio.search")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

DEFAULT_PROVIDERS = ["serper", "brave", "bing"]


def _normalize_urls(urls: List[str], limit: int) -> List[str]:
    normalized: list[str] = []
    for url in urls:
        if not url:
            continue
        if url.startswith("mailto:"):
            continue
        if url.startswith("javascript:"):
            continue
        if url.startswith("//"):
            url = f"https:{url}"
        if url.startswith("/"):
            continue
        normalized.append(url)
        if len(normalized) >= limit:
            break
    return normalized


class SearchDiscovery:
    CHALLENGE_PATTERNS = [
        "one last step",
        "please solve the challenge below",
        "security check",
        "are you human",
        "verify you are human",
        "please enable cookies",
        "press and hold the slider",
        "enter the characters you see",
    ]

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json, text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def rotate_user_agent(self) -> str:
        return random.choice(USER_AGENTS)

    def _rate_limit(self) -> None:
        time.sleep(settings.search_rate_limit_delay)

    def _is_bot_challenge(self, html: str) -> bool:
        if not html:
            return False
        lower = html.lower()
        if any(pattern in lower for pattern in self.CHALLENGE_PATTERNS):
            return True
        if "captcha" in lower and "bing" in lower:
            return True
        return False

    def discover(
        self,
        query: str,
        limit: int = 200,
        country: str | None = None,
        industry: str | None = None,
        providers: list[str] | None = None,
    ) -> List[str]:
        providers = providers or DEFAULT_PROVIDERS
        queries = self.build_search_queries(query, country=country, industry=industry)
        results: list[str] = []
        seen_domains: set[str] = set()

        for search_query in queries:
            if len(results) >= limit:
                break
            for provider in providers:
                if len(results) >= limit:
                    break
                if provider == "serper" and not settings.serper_api_key:
                    continue
                if provider == "brave" and not settings.brave_search_api_key:
                    continue

                try:
                    page_urls = self.search_provider(search_query, provider, limit - len(results))
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
        return [query.strip()] if query and query.strip() else []

    def search_provider(self, query: str, provider: str, limit: int) -> List[str]:
        if provider == "serper":
            return self.search_serper(query, limit)
        if provider == "brave":
            return self.search_brave(query, limit)
        if provider == "bing":
            return self.search_bing(query, limit)
        raise ValueError(f"Unsupported search provider: {provider}")

    def search_serper(self, query: str, limit: int) -> List[str]:
        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": settings.serper_api_key,
            "Accept": "application/json",
            "User-Agent": self.rotate_user_agent(),
        }
        params = {"q": query, "num": min(limit, 20)}
        data = self._fetch_json(url, headers=headers, params=params)
        return self.parse_serper_response(data, limit)

    def search_brave(self, query: str, limit: int) -> List[str]:
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "x-api-key": settings.brave_search_api_key,
            "Accept": "application/json",
            "User-Agent": self.rotate_user_agent(),
        }
        params = {"q": query, "size": min(limit, 20), "source": "web", "safesearch": "false"}
        data = self._fetch_json(url, headers=headers, params=params)
        return self.parse_brave_response(data, limit)

    def search_bing(self, query: str, limit: int) -> List[str]:
        url = "https://www.bing.com/search"
        headers = {
            "User-Agent": self.rotate_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
            "Referer": "https://www.bing.com/",
        }
        time.sleep(random.uniform(3, 7))
        params = {
            "q": query,
            "setlang": "en-IN",
            "cc": "IN",
        }
        html = self._fetch_html(url, headers=headers, params=params)
        print("=" * 50)
        print("QUERY:", query)
        print("HTML LENGTH:", len(html))
        print(html[:1000])
        print("=" * 50)

        if self._is_bot_challenge(html):
            logger.warning("Bing search blocked by anti-bot challenge for query '%s'", query)

        results = self.parse_bing_results(html)
        print("RESULTS FOUND:", len(results))
        if not results:
            logger.info("Bing HTML search returned no results for query '%s', trying Playwright fallback.", query)
            results = self.playwright_search(query, limit)
            print("PLAYWRIGHT RESULTS FOUND:", len(results))
        return _normalize_urls(results, limit)

    def _fetch_json(self, url: str, headers: dict[str, str], params: dict[str, str]) -> dict:
        raw_body = None
        for attempt in range(1, settings.search_max_retries + 1):
            self._rate_limit()
            self.session.headers.update({"User-Agent": self.rotate_user_agent()})
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=settings.request_timeout,
                    verify=True,
                )
                raw_body = self._log_response(response, url)
                response.raise_for_status()
                return response.json()
            except SSLError as exc:
                logger.warning("SSL validation failed for %s (attempt %s): %s", url, attempt, exc)
                try:
                    response = self.session.get(
                        url,
                        params=params,
                        headers=headers,
                        timeout=settings.request_timeout,
                        verify=False,
                    )
                    raw_body = self._log_response(response, url)
                    response.raise_for_status()
                    return response.json()
                except Exception:
                    raise
            except (ConnectionError, Timeout, HTTPError, RequestException) as exc:
                logger.warning("Search request failed for %s (attempt %s): %s", url, attempt, exc)
                if attempt == settings.search_max_retries:
                    raise
                time.sleep(settings.search_retry_backoff ** attempt)
        raise RuntimeError("Search API failed after retries")

    def _fetch_html(self, url: str, headers: dict[str, str], params: dict[str, str]) -> str:
        for attempt in range(1, settings.search_max_retries + 1):
            self._rate_limit()
            self.session.headers.update({"User-Agent": self.rotate_user_agent()})
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=settings.request_timeout,
                    verify=True,
                )
                self._log_response(response, url)
                response.raise_for_status()
                return response.text
            except SSLError as exc:
                logger.warning("SSL error for %s (attempt %s): %s", url, attempt, exc)
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=settings.request_timeout,
                    verify=False,
                )
                self._log_response(response, url)
                response.raise_for_status()
                return response.text
            except (ConnectionError, Timeout, HTTPError, RequestException) as exc:
                logger.warning("HTML request failed for %s (attempt %s): %s", url, attempt, exc)
                if attempt == settings.search_max_retries:
                    raise
                time.sleep(settings.search_retry_backoff ** attempt)
        raise RuntimeError("HTML search failed after retries")

    def _log_response(self, response: Response, url: str) -> str:
        raw_text = response.text
        truncated = raw_text[:4000] + ("..." if len(raw_text) > 4000 else "")
        logger.debug("Raw search response from %s: status=%s body=%s", url, response.status_code, truncated)
        return raw_text

    def parse_serper_response(self, data: dict, limit: int) -> List[str]:
        results: list[str] = []
        for item in data.get("organic", []) or []:
            href = item.get("link") or item.get("url")
            if href and not href.startswith("mailto:"):
                results.append(href)
                if len(results) >= limit:
                    break
        return results

    def parse_brave_response(self, data: dict, limit: int) -> List[str]:
        results: list[str] = []
        for item in data.get("web_results") or data.get("data") or data.get("results") or []:
            href = item.get("url") or item.get("link") or item.get("displayUrl")
            if href and not href.startswith("mailto:"):
                results.append(href)
                if len(results) >= limit:
                    break
        return results

    def parse_bing_results(self, html: str) -> List[str]:
        soup = BeautifulSoup(html, "lxml")
        links: list[str] = []
        selectors = ["#b_results .b_algo h2 a", ".b_algo h2 a", ".b_title a", ".b_entityTitle a", ".b_algo a"]

        for selector in selectors:
            for anchor in soup.select(selector):
                href = anchor.get("href")
                print("BING LINK:", href)
                if not href or href.startswith("mailto:"):
                    continue
                resolved = self._resolve_bing_url(href)
                if not resolved:
                    continue
                links.append(resolved)
            if links:
                return links

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            if href.startswith("mailto:") or href.startswith("javascript:"):
                continue
            resolved = self._resolve_bing_url(href)
            if resolved and resolved not in links:
                links.append(resolved)
        return links

    def _resolve_bing_url(self, href: str) -> str | None:
        if href.startswith("/"):
            href = f"https://www.bing.com{href}"

        if "bing.com/ck/a" in href or "/aclk" in href or "/rc?" in href or ("bing.com" in href and "u=" in href):
            try:
                parsed = urlparse(href)
                query = parse_qs(parsed.query)
                encoded = query.get("u", [None])[0]
                if encoded:
                    href = self._decode_bing_redirect(encoded)
            except Exception as exc:
                logger.debug("Could not unwrap Bing redirect URL %s: %s", href, exc)

        parsed = urlparse(href)
        if parsed.scheme not in {"http", "https"}:
            return None
        if parsed.netloc.endswith("bing.com"):
            return None
        return href

    def _decode_bing_redirect(self, encoded: str) -> str:
        if not encoded:
            return encoded
        if encoded.startswith("a1"):
            encoded = encoded[2:]
            padding = "=" * (-len(encoded) % 4)
            try:
                decoded = base64.b64decode(encoded + padding).decode("utf-8", errors="ignore")
                return decoded
            except Exception as exc:
                logger.debug("Failed to base64 decode Bing redirect token %s: %s", encoded, exc)
                return encoded
        return unquote(encoded)

    def playwright_search(self, query: str, limit: int) -> List[str]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning("Playwright is not installed; cannot use Playwright search fallback.")
            return []

        results: list[str] = []
        search_url = f"https://www.bing.com/search?q={quote(query)}&setlang=en-IN&cc=IN"
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=self.rotate_user_agent(),
                    locale="en-IN",
                    viewport={"width": 1280, "height": 800},
                    extra_http_headers={"Accept-Language": "en-IN,en;q=0.9", "Referer": "https://www.bing.com/"},
                )
                page = context.new_page()
                page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3000)
                content = page.content()
                if self._is_bot_challenge(content):
                    logger.warning("Bing search blocked by anti-bot challenge in Playwright for query '%s'", query)
                anchors = page.query_selector_all(".b_algo h2 a")
                if not anchors:
                    anchors = page.query_selector_all(".b_title a")
                for anchor in anchors:
                    href = anchor.get_attribute("href")
                    if not href or href.startswith("mailto:"):
                        continue
                    resolved = self._resolve_bing_url(href)
                    if resolved:
                        results.append(resolved)
                        if len(results) >= limit:
                            break
                if not results:
                    html = content
                    for anchor in BeautifulSoup(html, "lxml").find_all("a", href=True):
                        href = anchor["href"]
                        if href and not href.startswith("mailto:") and not href.startswith("javascript:"):
                            resolved = self._resolve_bing_url(href)
                            if resolved and resolved not in results:
                                results.append(resolved)
                                if len(results) >= limit:
                                    break
                context.close()
        except Exception as exc:
            logger.warning("Playwright fallback search failed for '%s': %s", query, exc)
        return results[:limit]
