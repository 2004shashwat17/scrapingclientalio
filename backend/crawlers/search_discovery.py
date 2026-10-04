import logging
import random
import re
import time
from typing import List
from urllib.parse import quote

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from backend.crawlers.browser import BrowserSession, CaptchaEncountered
from backend.crawlers.contact_extraction import (
    emails_in_text,
    infer_phone_region,
    normalize_phone,
)
from backend.crawlers.utils import is_blacklisted_domain, parse_domain
from backend.utils.settings import settings

logger = logging.getLogger("clientalio.search")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

PHONE_LINE_PATTERN = re.compile(r"^\+?[0-9][0-9\s\-().]{6,20}[0-9]$")
REVIEW_PATTERN = re.compile(r"([0-9]\.[0-9])\s*[·•]\s*([0-9,]+)\s*reviews?", re.I)

MAPS_URL_TEMPLATE = "https://www.google.com/maps/search/{query}"

# Google Maps chrome words that are not part of a real postal address.
UI_NOISE = {
    "saved", "save", "directions", "send to phone", "share", "photos",
    "reviews", "about", "search", "close", "copy link", "new", "edit",
    "claim this business", "add a missing place", "sign in", "menu",
    "options", "back", "next", "previous", "see all", "more", "less",
}

ADDRESS_MARKERS = (
    "street", "st", "road", "rd", "ave", "avenue", "boulevard", "blvd",
    "lane", "ln", "drive", "dr", "way", "plaza", "suite", "office",
    "floor", "tower", "building", "nagar", "sector", "marg", "cross",
)


def _looks_like_address(line: str) -> bool:
    """Reject Google UI labels and bare numbers; require a real street word."""
    lowered = line.lower().strip()
    if not lowered or lowered in UI_NOISE:
        return False
    if any(lowered.startswith(noise) for noise in ("directions", "send to phone", "claim this")):
        return False

    # Bare numbers are ratings, review counts or phone numbers, not addresses.
    if re.fullmatch(r"[\d.,\s:/\-()]+", lowered):
        return False
    if re.match(r"^\d+([.,]\d+)?\s*(stars|out of 5)?$", lowered):
        return False

    # Markers must match whole words: "st"/"rd"/"dr" are substrings of ordinary
    # words ("Logist-ics"), which previously produced false hits.
    tokens = set(re.findall(r"[a-z]+", lowered))
    if not tokens & set(ADDRESS_MARKERS):
        return False

    # Keep it address-shaped: a house/floor number, or a comma-separated line.
    return any(char.isdigit() for char in line) or "," in line


class SearchDiscovery:
    # One browser is shared for the whole run; a fresh one per query triggers captcha.
    _session: "BrowserSession | None" = None

    def rotate_user_agent(self) -> str:
        return random.choice(USER_AGENTS)

    def discover(
        self,
        query: str,
        limit: int = 200,
        country: str | None = None,
        industry: str | None = None,
        providers: list[str] | None = None,
    ) -> List[dict]:
        search_query = self.build_search_query(query, country=country, industry=industry)
        if not search_query:
            return []

        return self.scrape_google_maps(search_query, limit)

    def build_search_query(self, query: str, country: str | None = None, industry: str | None = None) -> str:
        search_query = query.strip() if query else ""
        if country:
            search_query = f"{search_query} {country.strip()}".strip()
        if industry:
            search_query = f"{search_query} {industry.strip()}".strip()
        return search_query

    def scrape_google_maps(self, search_query: str, limit: int) -> List[dict]:
        businesses: list[dict] = []

        session = self._session
        try:
            if session is None:
                session = self._open_session()
                self._session = session

            page = session.new_page()
            page.goto(MAPS_URL_TEMPLATE.format(query=quote(search_query)),
                      wait_until="domcontentloaded", timeout=45000)
            self._accept_cookies(page)
            session.wait_out_captcha(page, f"Maps '{search_query}'")
            self._wait_for_results(page)
            self._scroll_results(page, limit)

            cards_selector = "div[role='feed'] div[role='article']"
            cards = page.locator(cards_selector)
            count = cards.count()
            print("Business cards found:", count)

            place_urls: list[str] = []
            for index in range(min(count, limit * 2)):
                print("Inspecting business card", index + 1, "of", count)
                page.wait_for_selector(cards_selector, timeout=15000)
                card = cards.nth(index)
                place_url = self._find_card_place_url(card)
                if not place_url:
                    continue
                if place_url in place_urls:
                    continue
                place_urls.append(place_url)
                if len(place_urls) >= limit:
                    break

            for index, place_url in enumerate(place_urls, start=1):
                print("Processing business detail", index, "of", len(place_urls), place_url)
                # One page reused for every place, paced to look human.
                session.throttle()
                business = self._extract_business_from_place_url(session, place_url)
                if not business:
                    continue
                website = business.get("Website") or ""
                if website and is_blacklisted_domain(parse_domain(website)):
                    continue
                businesses.append(business)
                if len(businesses) >= limit:
                    break

            page.close()
        except CaptchaEncountered as exc:
            logger.warning("Maps blocked by captcha for '%s': %s", search_query, exc)
            print(f"  Stopping this keyword: {exc}")
        except PlaywrightTimeoutError as exc:
            logger.warning("Google Maps timeout for '%s': %s", search_query, exc)
        except Exception as exc:
            logger.warning("Google Maps scraping failed for '%s': %s", search_query, exc)

        return businesses

    def _open_session(self):
        """Create the shared browser session; closed by SearchDiscovery.close()."""
        session = BrowserSession()
        session.start()
        return session

    def close(self) -> None:
        """Release the shared browser at the end of a run."""
        if self._session is not None:
            self._session.close()
            self._session = None

    def _accept_cookies(self, page) -> None:
        labels = ["I agree", "Accept all", "Agree", "Accept"]
        for label in labels:
            try:
                button = page.get_by_role("button", name=label)
                if button.count() > 0:
                    button.first.click()
                    page.wait_for_timeout(1500)
                    return
            except Exception:
                continue

    def _wait_for_results(self, page) -> None:
        page.wait_for_timeout(4000)
        try:
            page.wait_for_selector("div[role='article']", timeout=30000)
        except PlaywrightTimeoutError:
            pass

    def _scroll_results(self, page, limit: int) -> None:
        last_count = 0
        for _ in range(20):
            results = page.locator("div[role='article']")
            current_count = results.count()
            if current_count >= limit and current_count == last_count:
                break
            if current_count > last_count:
                last_count = current_count
            page.evaluate(
                "() => { const feed = document.querySelector('[role=feed]'); if (feed) { feed.scrollTop = feed.scrollHeight; } window.scrollBy(0, window.innerHeight); }"
            )
            page.wait_for_timeout(1800)

    def _find_card_place_url(self, card) -> str | None:
        try:
            links = card.locator("a[href*='/maps/place/']")
            if links.count() > 0:
                href = links.first.get_attribute("href")
                if href:
                    href = href.strip()
                    if href.startswith("/"):
                        return f"https://www.google.com{href}"
                    return href
        except Exception:
            pass
        return None

    def _extract_business_from_place_url(self, session, place_url: str) -> dict | None:
        # Reuse one page for every place instead of opening a fresh context;
        # new contexts per request are a strong bot signal.
        page = session.new_page()
        try:
            page.goto(place_url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(2500)
            session.wait_out_captcha(page, f"place {place_url[-30:]}")
            page.wait_for_selector("h1, a:has-text('Website')", timeout=20000)
            body_text = page.inner_text("body")
            # A card without a website is still useful: name, phone and address
            # feed the enrichment chain, which searches Google for the site.
            website = self._find_website(page)
            if not website:
                logger.debug("No website on Maps card; will try to resolve it later")

            address = self._find_address(body_text)
            region = infer_phone_region(website, address)
            phone = self._find_phone_from_page(page, region) or self._find_phone(body_text, region)
            email = self._find_email(body_text)
            return {
                "CompanyName": self._find_business_name(page, body_text),
                "Website": website,
                "Phone": phone,
                "PhoneSource": "google_maps" if phone else "",
                "Location": address,
                "Email": email,
                "EmailSource": "google_maps" if email else "",
                "GoogleRating": self._find_rating(body_text),
                "GoogleReviewCount": self._find_review_count(body_text),
            }
        except Exception as exc:
            logger.debug("Failed to extract business from place URL %s: %s", place_url, exc)
            return None
        finally:
            try:
                page.close()
            except Exception:
                pass

    def _extract_business_from_card(self, page, card) -> dict | None:
        try:
            card.scroll_into_view_if_needed()
            page.wait_for_timeout(500)
            card.click(force=True)
            page.wait_for_timeout(1500)
            page.wait_for_selector("h1", timeout=10000)
        except Exception:
            return None

        body_text = page.inner_text("body")
        website = self._find_website(page)
        if not website:
            logger.debug("No website found after clicking business card")
            return None

        return {
            "CompanyName": self._find_business_name(page, body_text),
            "Website": website,
            "Phone": self._find_phone(body_text),
            "Location": self._find_address(body_text),
            "GoogleRating": self._find_rating(body_text),
            "GoogleReviewCount": self._find_review_count(body_text),
        }

    def _find_business_name(self, page, body_text: str) -> str:
        try:
            if page.locator("h1").count() > 0:
                name = page.locator("h1").first.inner_text().strip()
                if name:
                    return name
        except Exception:
            pass
        headline = body_text.splitlines()
        return headline[0].strip() if headline else ""

    def _find_website(self, page) -> str:
        try:
            link = page.get_by_role("link", name="Website").first
            if link.count() > 0:
                href = link.get_attribute("href")
                if href and href.startswith("http"):
                    return href.strip()
        except Exception:
            pass

        try:
            anchors = page.locator("a[href^='http']")
            total = anchors.count()
            for index in range(min(total, 20)):
                href = anchors.nth(index).get_attribute("href")
                if href and href.startswith("http") and "google.com" not in href and "maps.google.com" not in href:
                    return href.strip()
        except Exception:
            pass

        return ""

    def _find_email(self, text: str) -> str:
        """Maps rarely shows an email, but some listings do. Validated, never a placeholder."""
        found = emails_in_text(text or "")
        return found[0][0] if found else ""

    def _find_phone_from_page(self, page, region: str | None = None) -> str:
        """The listing's phone button carries the number as data-item-id='phone:tel:...'."""
        try:
            buttons = page.locator("[data-item-id^='phone:tel:']")
            for index in range(min(buttons.count(), 3)):
                item_id = buttons.nth(index).get_attribute("data-item-id") or ""
                phone = normalize_phone(item_id.removeprefix("phone:tel:"), region)
                if phone:
                    return phone
        except Exception:
            pass
        return ""

    def _find_phone(self, text: str, region: str | None = None) -> str:
        """Fallback: a body-text line that is entirely a phone number and validates."""
        for line in (text or "").splitlines():
            line = line.strip()
            if PHONE_LINE_PATTERN.match(line):
                phone = normalize_phone(line, region)
                if phone:
                    return phone
        return ""

    def _find_address(self, text: str) -> str:
        """Pull the postal address, ignoring Google UI chrome like 'Saved'."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        # Preferred: an explicit "Address" label, either inline or on the next line.
        for index, line in enumerate(lines):
            if "address" in line.lower():
                inline = re.split(r"address\s*:?", line, maxsplit=1, flags=re.I)
                if len(inline) > 1 and _looks_like_address(inline[1].strip()):
                    return inline[1].strip()
                for candidate in lines[index + 1: index + 4]:
                    if _looks_like_address(candidate):
                        return candidate

        # Otherwise the first line that actually reads like a postal address.
        for line in lines:
            if _looks_like_address(line):
                return line

        return ""

    def _find_rating(self, text: str) -> str:
        match = REVIEW_PATTERN.search(text)
        return match.group(1) if match else ""

    def _find_review_count(self, text: str) -> int:
        match = REVIEW_PATTERN.search(text)
        if match:
            count = match.group(2).replace(",", "")
            try:
                return int(count)
            except ValueError:
                return 0
        return 0
