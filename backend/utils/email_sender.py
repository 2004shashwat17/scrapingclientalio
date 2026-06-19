import json
import os
import re
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any

TEMPLATE_FILE = Path(__file__).resolve().parents[2] / "outreach_templates.json"

CATEGORY_TEMPLATE_MAP = {
    "Agency Founder": "TEMPLATE_1_AGENCIES",
    "Growth Agency Founder": "TEMPLATE_1_AGENCIES",
    "Digital Marketing Agency": "TEMPLATE_1_AGENCIES",
    "SEO Agency": "TEMPLATE_1_AGENCIES",
    "Web Development Agency": "TEMPLATE_1_AGENCIES",
    "UI/UX Agency": "TEMPLATE_1_AGENCIES",
    "SaaS Founder": "TEMPLATE_2_CEOS_FOUNDERS",
    "Business Coach": "TEMPLATE_3_FREELANCERS_CREATORS",
    "Career Coach": "TEMPLATE_3_FREELANCERS_CREATORS",
    "Executive Coach": "TEMPLATE_3_FREELANCERS_CREATORS",
    "Branding Consultant": "TEMPLATE_3_FREELANCERS_CREATORS",
    "Growth Consultant": "TEMPLATE_3_FREELANCERS_CREATORS",
    "HR Consultant": "TEMPLATE_3_FREELANCERS_CREATORS",
    "Recruitment Agency": "TEMPLATE_1_AGENCIES",
    "Personal Branding Expert": "TEMPLATE_3_FREELANCERS_CREATORS",
    "LinkedIn Ghostwriter": "TEMPLATE_3_FREELANCERS_CREATORS",
    "Product Leader": "TEMPLATE_2_CEOS_FOUNDERS",
    "Freelancer": "TEMPLATE_3_FREELANCERS_CREATORS",
    "Ignore": "TEMPLATE_3_FREELANCERS_CREATORS",
}

AGENCY_KEYWORDS = [
    "agency",
    "marketing",
    "seo",
    "digital",
    "branding",
    "web development",
    "creative",
    "advertising",
    "shopify",
]

FOUNDER_KEYWORDS = [
    "founder",
    "ceo",
    "co-founder",
    "entrepreneur",
    "managing director",
    "business owner",
    "startup",
    "saas",
]

FREELANCER_KEYWORDS = [
    "freelancer",
    "consultant",
    "coach",
    "designer",
    "copywriter",
    "developer",
    "personal brand",
    "service provider",
]


def load_templates(path: Path | str = TEMPLATE_FILE) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_text(text: str) -> str:
    return str(text or "").strip()


def choose_template(category: str | None) -> str:
    if not category:
        return "TEMPLATE_3_FREELANCERS_CREATORS"
    return CATEGORY_TEMPLATE_MAP.get(category, "TEMPLATE_3_FREELANCERS_CREATORS")


def build_personalized_intro(name: str, company: str | None, category: str | None) -> str:
    company = normalize_text(company)
    category_text = normalize_text(category).lower()
    if category and any(keyword in category_text for keyword in AGENCY_KEYWORDS):
        return "Looks like you're helping brands grow through digital marketing and client services."
    if category and any(keyword in category_text for keyword in FOUNDER_KEYWORDS):
        if company:
            return f"Looks like you're building {company} and growing the business."
        return "Looks like you're building and growing the business."
    return "Looks like you're helping clients through your expertise and services."


def fill_template(template: str, name: str, company: str | None) -> str:
    email = template.replace("{{Name}}", normalize_text(name))
    if company:
        email = email.replace("{{CompanyName}}", normalize_text(company))
    return email


def is_valid_email(email: str | None) -> bool:
    if not email:
        return False
    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    return bool(re.match(pattern, email.strip()))


def build_message(
    sender: str,
    recipient: str,
    subject: str,
    body: str,
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    return message


def send_gmail(
    sender_email: str,
    sender_password: str,
    recipient_email: str,
    subject: str,
    body: str,
) -> None:
    if not is_valid_email(sender_email):
        raise ValueError("Invalid sender email address")
    if not is_valid_email(recipient_email):
        raise ValueError("Invalid recipient email address")

    message = build_message(sender_email, recipient_email, subject, body)
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(sender_email, sender_password)
        smtp.send_message(message)


def build_outreach_email(
    name: str,
    recipient_email: str,
    company: str | None = None,
    category: str | None = None,
    template_key: str | None = None,
) -> dict[str, Any]:
    templates = load_templates()
    template_key = template_key or choose_template(category)
    template_text = templates.get(template_key, templates["TEMPLATE_3_FREELANCERS_CREATORS"])
    body = fill_template(template_text, name, company)
    intro = build_personalized_intro(name, company, category)
    subject = "Quick question about client testimonials"
    return {
        "recipient": recipient_email,
        "subject": subject,
        "body": body,
        "personalized_intro": intro,
        "template_key": template_key,
    }
