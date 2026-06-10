from typing import Dict


INDUSTRY_SCORES = {
    "marketing agency": 20,
    "seo agency": 20,
    "web development agency": 20,
    "web development": 20,
    "saas company": 15,
    "saas": 15,
}


def calculate_lead_score(industry: str | None, flags: Dict[str, bool]) -> int:
    score = 0
    if industry:
        normalized = industry.strip().lower()
        for key, value in INDUSTRY_SCORES.items():
            if key in normalized:
                score += value
    if flags.get("HasTestimonials"):
        score += 20
    if flags.get("HasVideoTestimonials"):
        score += 20
    if flags.get("HasCaseStudies"):
        score += 10
    if flags.get("HasGoogleReviews"):
        score += 10
    if not flags.get("HasTestimonials"):
        score -= 20
    return max(0, min(score, 100))


def translate_priority(score: int) -> str:
    if score >= 80:
        return "Hot Lead"
    if score >= 60:
        return "Warm Lead"
    if score >= 40:
        return "Medium Lead"
    return "Low Priority"
