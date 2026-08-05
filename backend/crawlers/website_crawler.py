import json
import logging
import re
from typing import Any

import requests
from bs4 import BeautifulSoup

from backend.crawlers.utils import (
    choose_best_business_email,
    choose_best_phone,
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

    def _extract_pattern_value(self, text: str, patterns: list[str]) -> str:
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                value = next((group for group in match.groups() if group), "")
                cleaned = re.sub(r"\s+", " ", value).strip(" .:-")
                if cleaned:
                    return cleaned
        return ""

    def _extract_cities_served(self, text: str) -> str:
        return self._extract_pattern_value(
            text,
            [
                r"(?:serving|we serve|service areas?|coverage(?: includes)?|operating in)\s+([^.\n]{8,140})",
                r"(?:cities served|service locations?)\s*[:\-]\s*([^.\n]{5,140})",
            ],
        )

    def _extract_fleet_size(self, text: str) -> str:
        return self._extract_pattern_value(
            text,
            [
                r"fleet(?: size)?\s*(?:of|:)?\s*(\d[\d,\.]{0,18}\+?)",
                r"(\d[\d,\.]{0,18}\+?)\s+(?:vehicles|trucks|vans|drivers?)",
            ],
        )

    def _extract_employees(self, text: str) -> str:
        return self._extract_pattern_value(
            text,
            [
                r"(?:team of|staff of|employees?\s*(?:count)?\s*(?:of|:)?|workforce\s*(?:of|:)?|about)\s*(\d[\d,\.]{0,18}\+?)\s*(?:employees?|people|team members|staff)",
                r"(\d[\d,\.]{0,18}\+?)\s*(?:employees?|team members|staff)",
            ],
        )

    def _extract_revenue(self, text: str) -> str:
        return self._extract_pattern_value(
            text,
            [
                r"(?:annual\s+)?(?:revenue|turnover)\s*(?:of|:)?\s*([$€£]|usd|eur|inr)?\s*([\d,\.]+\s*(?:million|billion|m|bn|crore|lakh)?)",
            ],
        )

    def _extract_delivery_volume(self, text: str) -> str:
        return self._extract_pattern_value(
            text,
            [
                r"(?:delivery volume|deliveries per (?:day|week|month|year)|shipments per (?:day|week|month|year))\s*(?:of|:)?\s*([\d,\.]+\+?\s*(?:per\s*(?:day|week|month|year))?)",
            ],
        )

    def _extract_crm_tms(self, text: str) -> str:
        known_tools = [
            "Salesforce",
            "HubSpot",
            "Zoho",
            "Pipedrive",
            "Dynamics 365",
            "NetSuite",
            "SAP",
            "Oracle",
            "Manhattan",
            "Descartes",
            "project44",
            "Shipwell",
            "Onfleet",
        ]
        lowered = text.lower()
        found = [tool for tool in known_tools if tool.lower() in lowered]
        if found:
            return ", ".join(found)
        return self._extract_pattern_value(
            text,
            [r"(?:crm|tms)\s*(?:platform|software|tool|stack)?\s*(?:used|in use|:)?\s*([^.\n]{3,80})"],
        )

    def _extract_existing_pod_solution(self, text: str) -> str:
        lowered = text.lower()
        pod_markers = [
            "proof of delivery",
            "electronic pod",
            "pod app",
            "delivery confirmation",
        ]
        if any(marker in lowered for marker in pod_markers):
            return self._extract_pattern_value(
                text,
                [r"(?:proof of delivery|electronic pod|pod solution)\s*(?:using|with|:)?\s*([^.\n]{3,80})"],
            ) or "Mentioned on website"
        return ""

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
        best_email, _, _ = choose_best_business_email(emails, website, decision_maker_name)
        if designation and designation not in {"Founder", "Co-Founder", "CEO", "Owner", "Managing Director", "Director"}:
            designation = "Unknown"
        best_phone, _ = choose_best_phone(phones)
        social_links = find_social_links(soup, website)
        company_name = self.extract_company_name(soup, website)
        location = extract_location(all_text)
        cities_served = self._extract_cities_served(all_text)
        fleet_size_public = self._extract_fleet_size(all_text)
        employees = self._extract_employees(all_text)
        revenue_public = self._extract_revenue(all_text)
        crm_tms_used_public = self._extract_crm_tms(all_text)
        delivery_volume_public = self._extract_delivery_volume(all_text)
        existing_pod_solution = self._extract_existing_pod_solution(all_text)

        decision_makers = ""
        if decision_maker_name and designation and designation != "Unknown":
            decision_makers = f"{decision_maker_name} ({designation})"
        elif decision_maker_name:
            decision_makers = decision_maker_name

        if len(all_text) < 500 and any(marker in homepage_html for marker in ["<script", "window."]):
            rendered_html = self.render_page_with_selenium(website)
            if rendered_html:
                rendered_soup = self.parse_page(rendered_html, website)
                all_text = rendered_soup.get_text(separator=" \n")
                emails = extract_emails(all_text)
                phones = extract_phones(all_text)
                decision_maker_name, designation = extract_decision_maker(all_text)
                best_email, _, _ = choose_best_business_email(emails, website, decision_maker_name)
                best_phone, _ = choose_best_phone(phones)
                social_links = {**social_links, **find_social_links(rendered_soup, website)}
                location = location or extract_location(all_text)
                decision_maker_name, designation = decision_maker_name or extract_decision_maker(all_text)
                cities_served = cities_served or self._extract_cities_served(all_text)
                fleet_size_public = fleet_size_public or self._extract_fleet_size(all_text)
                employees = employees or self._extract_employees(all_text)
                revenue_public = revenue_public or self._extract_revenue(all_text)
                crm_tms_used_public = crm_tms_used_public or self._extract_crm_tms(all_text)
                delivery_volume_public = delivery_volume_public or self._extract_delivery_volume(all_text)
                existing_pod_solution = existing_pod_solution or self._extract_existing_pod_solution(all_text)
                if not decision_makers:
                    if decision_maker_name and designation and designation != "Unknown":
                        decision_makers = f"{decision_maker_name} ({designation})"
                    elif decision_maker_name:
                        decision_makers = decision_maker_name

        business_page_links = bool(service_page or product_page)
        if not has_business_pages(page_urls) and not is_business_website(all_text, business_page_links):
            raise ValueError("Website does not appear to be a valid business website")

        notes_parts: list[str] = []
        if source_keyword:
            notes_parts.append(f"Source keyword: {source_keyword}")
        if contact_page:
            notes_parts.append(f"Contact page: {normalize_url(website, contact_page)}")
        notes = " | ".join(notes_parts)

        return {
            "CompanyName": company_name,
            "Website": website,
            "Headquarters": address or location,
            "CitiesServed": cities_served,
            "Industry": industry or "",
            "FleetSizePublic": fleet_size_public,
            "Employees": employees,
            "RevenuePublic": revenue_public,
            "DecisionMakers": decision_makers,
            "LinkedInURL": social_links.get("LinkedIn"),
            "Email": best_email,
            "Phone": best_phone,
            "CRMTMSUsedPublic": crm_tms_used_public,
            "DeliveryVolumePublic": delivery_volume_public,
            "ExistingPODSolution": existing_pod_solution,
            "Notes": notes,
        }
