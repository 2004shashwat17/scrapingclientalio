"""Google web search (SERP) used to find a company's website when Maps has none.

Reuses the same Playwright setup as SearchDiscovery, so a visible run shows the
search happening in a real browser window.
"""

import logging
from urllib.parse import parse_qs, quote, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from backend.crawlers.browser import BrowserSession, CaptchaEncountered, DEFAULT_UA
from backend.utils.settings import settings

logger = logging.getLogger("clientalio.websearch")

SEARCH_URL_TEMPLATE = "https://www.google.com/search?q={query}&num=20"
DDG_URL = "https://html.duckduckgo.com/html/"

# Hosts Google wraps its result links in; these are not the destination sites.
GOOGLE_HOSTS = ("google.", "googleusercontent.", "gstatic.", "youtube.com", "maps.google.")

# DuckDuckGo routes sponsored results through its own domain; never a real lead site.
DDG_INTERNAL = ("duckduckgo.com/", "ad_provider=", "ad_domain=")

SOCIAL_HOSTS = {
    "facebook.com": "Facebook",
    "fb.com": "Facebook",
    "instagram.com": "Instagram",
    "twitter.com": "Twitter",
    "x.com": "Twitter",
    "linkedin.com": "LinkedIn",
    "youtube.com": "YouTube",
    "wa.me": "WhatsApp",
}


class GoogleWebSearch:
    """Scrape organic results, sharing one browser with the rest of the run."""

    def __init__(self, session: BrowserSession | None = None) -> None:
        self._session = session
        # Latches when connectivity fails, so we stop wasting browser launches.
        self._network_down = False
        # Plain HTTP client for the DuckDuckGo path; no browser page needed.
        self._session_http = requests.Session()
        self._session_http.headers.update({
            "User-Agent": settings.browser_user_agent or DEFAULT_UA,
            "Accept-Language": "en-US,en;q=0.9",
        })

    def set_session(self, session: BrowserSession) -> None:
        """Reuse the run's browser so cookies and fingerprint stay consistent."""
        self._session = session

    @property
    def session(self) -> BrowserSession:
        if self._session is None:
            self._session = BrowserSession()
            self._session.start()
        return self._session

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """Return [{title, url, snippet}] for `query`.

        DuckDuckGo's HTML endpoint is tried first: it is a plain HTTP request,
        so it costs no browser page and is far less likely to trigger a captcha.
        Google is only used if DuckDuckGo returns nothing.
        """
        if not query or not query.strip():
            return []

        results = self._search_duckduckgo(query, limit)
        if results:
            self._network_down = False
            logger.info("DuckDuckGo returned %d results for '%s'", len(results), query)
            return results

        if self._network_down:
            # Connectivity is broken; skip the browser entirely this round.
            logger.warning("Skipping Google fallback, network appears unavailable")
            return []

        logger.info("Falling back to Google for '%s'", query)
        return self._search_google(query, limit)

    def _search_duckduckgo(self, query: str, limit: int) -> list[dict]:
        """Scrape DuckDuckGo's lightweight HTML endpoint."""
        try:
            response = self._session_http.get(
                DDG_URL, params={"q": query.strip()}, timeout=settings.request_timeout
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            # Network/DNS trouble: no point burning a browser page on Google too.
            logger.warning("DuckDuckGo search failed for '%s': %s", query, exc)
            self._network_down = True
            return []
        except Exception as exc:
            logger.warning("DuckDuckGo search failed for '%s': %s", query, exc)
            return []

        soup = BeautifulSoup(response.text, "lxml")
        results: list[dict] = []
        seen: set[str] = set()

        for node in soup.select("div.result, div.web-result"):
            anchor = node.select_one("a.result__a")
            if not anchor:
                continue
            href = self._unwrap(anchor.get("href", ""))
            if not href or href in seen or self._is_google_internal(href):
                continue
            snippet_node = node.select_one(".result__snippet")
            seen.add(href)
            results.append({
                "title": anchor.get_text(strip=True),
                "url": href,
                "snippet": snippet_node.get_text(strip=True) if snippet_node else "",
            })
            if len(results) >= limit:
                break

        return results

    def _search_google(self, query: str, limit: int) -> list[dict]:
        """Scrape Google as a fallback, sharing the run's browser session."""
        url = SEARCH_URL_TEMPLATE.format(query=quote(query.strip()))
        results: list[dict] = []
        seen: set[str] = set()
        page = None

        try:
            self.session.throttle()
            page = self.session.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            self._accept_consent(page)
            self.session.wait_out_captcha(page, f"search '{query[:30]}'")
            page.wait_for_timeout(2000)

            # Google renders results client-side now, so walk anchors rather
            # than relying on the old div.g/h3 markup that no longer exists.
            anchors = page.locator("#search a[href]")
            total = anchors.count()
            for index in range(total):
                href = anchors.nth(index).get_attribute("href") or ""
                href = self._unwrap(href)
                if not href or href in seen or self._is_google_internal(href):
                    continue
                seen.add(href)
                results.append({"title": "", "url": href, "snippet": ""})
                if len(results) >= limit:
                    break
        except CaptchaEncountered as exc:
            logger.warning("Search blocked by captcha for '%s': %s", query, exc)
            print(f"  Skipping enrichment for '{query[:30]}': {exc}")
        except Exception as exc:
            logger.warning("Google web search failed for '%s': %s", query, exc)
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    logger.debug("Could not close search page", exc_info=True)

        return results

    def _accept_consent(self, page) -> None:
        for label in ("I agree", "Accept all", "Accept", "Reject all"):
            try:
                button = page.get_by_role("button", name=label)
                if button.count() > 0:
                    button.first.click()
                    page.wait_for_timeout(1200)
                    return
            except Exception:
                continue

    def _collect_results(self, page) -> list[tuple[str, str, str]]:
        """Pull (title, url, snippet) from the result blocks, tolerating markup changes."""
        collected: list[tuple[str, str, str]] = []
        blocks = page.locator("div.g, div[data-hveid]")
        total = blocks.count()
        for index in range(min(total, 60)):
            block = blocks.nth(index)
            try:
                heading = block.locator("h3").first
                if heading.count() == 0:
                    continue
                anchor = heading.locator("xpath=ancestor::a[1]")
                if anchor.count() == 0:
                    continue
                href = anchor.get_attribute("href") or ""
                title = heading.inner_text().strip()
                snippet = ""
                try:
                    snippet = block.inner_text().strip()[:400]
                except Exception:
                    snippet = ""
                href = self._unwrap(href)
                if href and title:
                    collected.append((title, href, snippet))
            except Exception:
                continue
        return collected

    @staticmethod
    def _unwrap(href: str) -> str:
        """Resolve redirect wrappers to the real destination URL."""
        if not href:
            return ""
        # DuckDuckGo: //duckduckgo.com/l/?uddg=<urlencoded>
        if "duckduckgo.com/l/" in href or href.startswith("//duckduckgo.com/l/"):
            parsed = urlparse(href if href.startswith("http") else f"https:{href}")
            target = parse_qs(parsed.query).get("uddg") or []
            if target:
                return unquote(target[0])
        # Google: /url?q=<url> or google.com/redirect?q=<url>
        if href.startswith("/url?") or ("google." in href and "/url?" in href):
            parsed = parse_qs(urlparse(href).query)
            target = parsed.get("q") or []
            if target:
                return unquote(target[0])
        return href

    @staticmethod
    def _is_google_internal(url: str) -> bool:
        """True for search-engine plumbing that is not the company's real site."""
        if not url:
            return True
        if any(token in url for token in DDG_INTERNAL):
            return True
        netloc = urlparse(url).netloc.lower()
        if any(netloc.endswith(host) or host in netloc for host in GOOGLE_HOSTS):
            return True
        return url.startswith("/") or not url.startswith("http")

    @staticmethod
    def social_kind(url: str) -> str | None:
        """Return 'LinkedIn'/'Facebook'/... if the URL points at a social profile."""
        netloc = urlparse(url).netloc.lower().removeprefix("www.")
        for host, label in SOCIAL_HOSTS.items():
            if netloc == host or netloc.endswith(f".{host}"):
                return label
        return None


def company_search_queries(company_name: str, location: str | None = None) -> list[str]:
    """Search strings to try, most specific first."""
    name = (company_name or "").strip()
    place = (location or "").strip()
    queries = []
    if name and place:
        queries.append(f'"{name}" {place}')
    if name:
        queries.append(f'"{name}"')
        queries.append(f"{name} official website")
        queries.append(f"{name} contact")
    return queries