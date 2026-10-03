"""Shared browser session for Google, used by both Maps and web search.

Why this exists: launching a fresh browser per query looks nothing like a human,
so Google throws a captcha almost immediately. Here we keep ONE persistent
Chromium profile for the whole run, which:

- reuses cookies and the consent decision across keywords and across runs,
- keeps a single stable user agent instead of rotating it per query,
- lets a human solve a captcha once in the visible window and carry on.
"""

import logging
import random
import time
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import sync_playwright

from backend.utils.settings import settings

logger = logging.getLogger("clientalio.browser")

# Markers Google shows instead of results when it is suspicious.
CAPTCHA_MARKERS = (
    "unusual traffic",
    "not a robot",
    "our systems have detected",
    "recaptcha",
    "unusual traffic from your computer network",
)

LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
]

# A stable, ordinary desktop Chrome UA. Rotating this per request is a red flag.
DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


class CaptchaEncountered(Exception):
    """Raised when Google shows a captcha we could not get past."""


def captcha_visible(page) -> bool:
    """True if a captcha / bot-check interstitial is on screen."""
    try:
        if page.locator("iframe[src*='recaptcha']").count() > 0:
            return True
        if page.locator("#captcha-form, div#recaptcha").count() > 0:
            return True
        text = page.inner_text("body")[:2000].lower()
        return any(marker in text for marker in CAPTCHA_MARKERS)
    except Exception:
        return False


class BrowserSession:
    """One persistent Chromium profile, reused for every query in a run."""

    def __init__(self) -> None:
        self._pw = None
        self._context = None
        self.profile_dir = Path(settings.browser_profile_dir).expanduser().resolve()

    def start(self):
        if self._context is not None:
            return self._context

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        # A persistent profile keeps cookies/consent, so Google trusts us more.
        self._context = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            headless=settings.headless,
            slow_mo=settings.browser_slow_mo_ms,
            args=LAUNCH_ARGS,
            viewport={"width": 1400, "height": 900},
            locale="en-US",
            user_agent=settings.browser_user_agent or DEFAULT_UA,
        )
        self._context.set_default_timeout(45000)
        logger.info("Browser session started (profile: %s)", self.profile_dir.name)
        return self._context

    def new_page(self):
        return self.start().new_page()

    def throttle(self) -> None:
        """Randomised pause between requests; the old cadence was machine-like."""
        base = settings.browser_request_delay
        if base <= 0:
            return
        delay = base + random.uniform(0, base * 0.6)
        logger.debug("Throttling %.1fs", delay)
        time.sleep(delay)

    def wait_out_captcha(self, page, label: str) -> None:
        """If a captcha appears, pause so it can be solved by hand.

        In a visible run the human clicks the checkbox and we continue. Headless
        runs cannot solve it, so we raise and the caller backs off.
        """
        if not captcha_visible(page):
            return

        if settings.headless:
            raise CaptchaEncountered(
                "Google showed a captcha. Run with a visible browser and solve it once."
            )

        logger.warning("Captcha on %s - solve it in the browser window.", label)
        print(
            "\n  !! Google is asking for a captcha.\n"
            "     Please solve it in the browser window that just opened.\n"
            "     This run continues automatically once it clears.\n"
        )
        deadline = time.time() + settings.captcha_wait_seconds
        while time.time() < deadline:
            if not captcha_visible(page):
                print("  Captcha cleared, continuing.")
                return
            time.sleep(2)

        raise CaptchaEncountered(
            f"Captcha not cleared within {settings.captcha_wait_seconds}s."
        )

    def close(self) -> None:
        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                logger.debug("Error closing browser context", exc_info=True)
            self._context = None
        if self._pw is not None:
            try:
                self._pw.stop()
            except Exception:
                logger.debug("Error stopping playwright", exc_info=True)
            self._pw = None


@contextmanager
def browser_session():
    """Session that is reused across the run and always closed at the end."""
    session = BrowserSession()
    try:
        yield session
    finally:
        session.close()
# PLACEHOLDER