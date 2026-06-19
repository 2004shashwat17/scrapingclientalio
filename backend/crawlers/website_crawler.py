import json
import logging
import re
from urllib.parse import urljoin
from typing import Any

import requests
from bs4 import BeautifulSoup

from backend.crawlers.utils import (
    choose_best_business_email,
    choose_best_phone,
    detect_social_proof,
    extract_emails,
    extract_phones,
    extract_decision_maker,
    extract_location,
    find_page_urls,
    find_social_links,
    has_business_pages,
    is_business_website,
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
        name = self._extract_json_ld_org_name(soup)
        if name:
            return name
        name = self._extract_open_graph_name(soup)
        if name:
            return name
        name = self._extract_logo_alt_text(soup)
        if name:
            return name
        header = soup.find("h1")
        if header and header.get_text(strip=True):
            return header.get_text(strip=True)
        if title := soup.title and title.string:
            cleaned = title.string.strip()
            return self._clean_title_name(cleaned, base_url)
        return parse_domain(base_url)

    def _extract_json_ld_org_name(self, soup: BeautifulSoup) -> str | None:
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string or "{}").copy()
            except Exception:
                continue
            if isinstance(data, list):
                items = data
            else:
                items = [data]
            for item in items:
                if item.get("@type") in {"Organization", "Corporation", "LocalBusiness", "ProfessionalService"}:
                    name = item.get("name")
                    if name:
                        return name.strip()
        return None

    def _extract_open_graph_name(self, soup: BeautifulSoup) -> str | None:
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"].strip()
        return None

    def _extract_logo_alt_text(self, soup: BeautifulSoup) -> str | None:
        for img in soup.find_all("img", alt=True):
            alt = img["alt"].strip()
            if alt and len(alt) < 100 and "logo" not in alt.lower():
                return alt
        return None

    def _clean_title_name(self, title: str, base_url: str) -> str:
        domain = parse_domain(base_url)
        parts = [part.strip() for part in re.split(r"[\|\-–—»]", title) if part.strip()]
        if len(parts) > 1:
            for part in parts:
                if not any(exclude in part.lower() for exclude in ["home", "welcome", "page", domain.lower()]):
                    return part
            return parts[0]
        return title

    def extract_contact_page(self, base_url: str, soup: BeautifulSoup) -> str | None:
        page_urls = find_page_urls(base_url, soup)
        return page_urls.get("contact")

    def crawl(self, website: str, industry: str | None = None, source_keyword: str | None = None, address: str | None = None) -> dict[str, Any]:
        website = website.strip()
        if not website.startswith("http"):
            website = f"https://{website}"

        homepage_html = self.fetch(website)
        soup = self.parse_page(homepage_html, website)
        page_urls = find_page_urls(website, soup)
        contact_page = page_urls.get("contact")
        about_page = page_urls.get("about")
        team_page = page_urls.get("team")
        leadership_page = page_urls.get("leadership")
        service_page = page_urls.get("services")
        product_page = page_urls.get("products")
        testimonial_page = page_urls.get("testimonials")
        reviews_page = page_urls.get("reviews")
        case_study_page = page_urls.get("case_studies")

        candidate_pages = {
            "ContactPage": contact_page,
            "AboutPage": about_page,
            "TeamPage": team_page,
            "LeadershipPage": leadership_page,
            "ServicesPage": service_page,
            "ProductsPage": product_page,
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

        decision_text = "\n".join(
            page_contents.get(key, "")
            for key in ["AboutPage", "TeamPage", "LeadershipPage", "ContactPage"]
            if page_contents.get(key)
        )
        all_text = "\n".join(page_contents.values())
        contact_emails = extract_emails(page_contents.get("ContactPage", ""))
        emails = contact_emails or extract_emails(all_text)
        phones = extract_phones(all_text)
        decision_maker_name, designation = extract_decision_maker(decision_text or all_text)
        best_email, email_type, email_confidence = choose_best_business_email(emails, website, decision_maker_name)
        if designation and designation not in {"Founder", "Co-Founder", "CEO", "Owner", "Managing Director", "Director"}:
            designation = "Unknown"
        best_phone, phone_confidence = choose_best_phone(phones)
        social_links = find_social_links(soup)
        company_name = self.extract_company_name(soup, website)
        contact_url = normalize_url(website, contact_page) if contact_page else None
        proof_flags = detect_social_proof(all_text)
        location = extract_location(all_text)

        if len(all_text) < 500 and any(marker in homepage_html for marker in ["<script", "window."]):
            rendered_html = self.render_page_with_selenium(website)
            if rendered_html:
                rendered_soup = self.parse_page(rendered_html, website)
                all_text = rendered_soup.get_text(separator=" \n")
                emails = extract_emails(all_text)
                phones = extract_phones(all_text)
                decision_maker_name, designation = extract_decision_maker(all_text)
                best_email, email_type, email_confidence = choose_best_business_email(emails, website, decision_maker_name)
                best_phone, phone_confidence = choose_best_phone(phones)
                social_links = {**social_links, **find_social_links(rendered_soup)}
                proof_flags = detect_social_proof(all_text)
                location = location or extract_location(all_text)
                decision_maker_name, designation = decision_maker_name or extract_decision_maker(all_text)

        business_page_links = bool(service_page or product_page)
        if not has_business_pages(page_urls) and not is_business_website(all_text, business_page_links):
            raise ValueError("Website does not appear to be a valid business website")

        return {
            "CompanyName": company_name,
            "Website": website,
            "Industry": industry or "",
            "Location": location,
            "Address": address or location,
            "DecisionMakerName": decision_maker_name or "",
            "Designation": designation or "",
            "Email": best_email,
            "EmailType": email_type or "",
            "Phone": best_phone,
            "LinkedIn": social_links.get("LinkedIn"),
            "Facebook": social_links.get("Facebook"),
            "Instagram": social_links.get("Instagram"),
            "Twitter": social_links.get("Twitter"),
            "YouTube": social_links.get("YouTube"),
            "ContactPage": contact_url,
            "SourceKeyword": source_keyword or "",
            "HasTestimonials": proof_flags["HasTestimonials"],
            "HasVideoTestimonials": proof_flags["HasVideoTestimonials"],
            "HasCaseStudies": proof_flags["HasCaseStudies"],
            "HasGoogleReviews": proof_flags["HasGoogleReviews"],
        }
