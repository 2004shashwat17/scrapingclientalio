import logging
import re
from urllib.parse import urljoin
from typing import Any

import requests
from bs4 import BeautifulSoup

from backend.crawlers.utils import (
    choose_best_email,
    choose_best_phone,
    detect_social_proof,
    extract_emails,
    extract_phones,
    find_page_urls,
    find_social_links,
    normalize_url,
    parse_domain,
)
from backend.utils.settings import settings

logger = logging.getLogger("clientalio.crawler")


class WebsiteCrawler:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": settings.user_agent})

    def fetch(self, url: str) -> str:
        for attempt in range(settings.max_crawl_retries + 1):
            try:
                response = self.session.get(url, timeout=settings.request_timeout)
                response.raise_for_status()
                return response.text
            except Exception as exc:
                logger.warning("Fetch failed %s attempt %s: %s", url, attempt + 1, exc)
                if attempt == settings.max_crawl_retries:
                    raise
        raise RuntimeError("Unable to fetch page")

    def render_page_with_selenium(self, url: str) -> str | None:
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options

            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            driver = webdriver.Chrome(options=options)
            driver.get(url)
            html = driver.page_source
            driver.quit()
            return html
        except Exception as exc:
            logger.warning("Selenium render failed for %s: %s", url, exc)
            return None

    def parse_page(self, html: str, base_url: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    def extract_company_name(self, soup: BeautifulSoup, base_url: str) -> str:
        if title := soup.title and soup.title.string:
            return title.string.strip()
        header = soup.find(["h1", "h2"])
        if header and header.get_text(strip=True):
            return header.get_text(strip=True)
        return parse_domain(base_url)

    def extract_contact_page(self, base_url: str, soup: BeautifulSoup) -> str | None:
        page_urls = find_page_urls(base_url, soup)
        return page_urls.get("contact")

    def crawl(self, website: str, industry: str | None = None) -> dict[str, Any]:
        website = website.strip()
        if not website.startswith("http"):
            website = f"https://{website}"

        homepage_html = self.fetch(website)
        soup = self.parse_page(homepage_html, website)
        page_urls = find_page_urls(website, soup)
        contact_page = page_urls.get("contact")
        about_page = page_urls.get("about")
        testimonial_page = page_urls.get("testimonials")
        reviews_page = page_urls.get("reviews")
        case_study_page = page_urls.get("case_studies")

        candidate_pages = {
            "ContactPage": contact_page,
            "AboutPage": about_page,
            "TestimonialsPage": testimonial_page,
            "ReviewsPage": reviews_page,
            "CaseStudiesPage": case_study_page,
        }

        page_contents = {"homepage": homepage_html}
        for label, page_url in candidate_pages.items():
            if page_url:
                try:
                    page_contents[label] = self.fetch(page_url)
                except Exception:
                    logger.info("Could not fetch page: %s", page_url)

        all_text = "\n".join(page_contents.values())
        emails = extract_emails(all_text)
        phones = extract_phones(all_text)
        best_email, email_confidence = choose_best_email(emails, website)
        best_phone, phone_confidence = choose_best_phone(phones)
        social_links = find_social_links(soup)
        company_name = self.extract_company_name(soup, website)
        contact_url = normalize_url(website, contact_page) if contact_page else None
        proof_flags = detect_social_proof(all_text)

        if len(all_text) < 500 and any(marker in homepage_html for marker in ["<script", "window."]):
            rendered_html = self.render_page_with_selenium(website)
            if rendered_html:
                rendered_soup = self.parse_page(rendered_html, website)
                all_text = rendered_soup.get_text(separator=" \n")
                emails = extract_emails(all_text)
                phones = extract_phones(all_text)
                best_email, email_confidence = choose_best_email(emails, website)
                best_phone, phone_confidence = choose_best_phone(phones)
                social_links = {**social_links, **find_social_links(rendered_soup)}
                proof_flags = detect_social_proof(all_text)

        return {
            "CompanyName": company_name,
            "Website": website,
            "Industry": industry or "",
            "Email": best_email,
            "Phone": best_phone,
            "LinkedIn": social_links.get("LinkedIn"),
            "Facebook": social_links.get("Facebook"),
            "Instagram": social_links.get("Instagram"),
            "Twitter": social_links.get("Twitter"),
            "YouTube": social_links.get("YouTube"),
            "ContactPage": contact_url,
            "HasTestimonials": proof_flags["HasTestimonials"],
            "HasVideoTestimonials": proof_flags["HasVideoTestimonials"],
            "HasCaseStudies": proof_flags["HasCaseStudies"],
            "HasGoogleReviews": proof_flags["HasGoogleReviews"],
        }
