"""Offline checks for the enrichment chain. No network, no browser."""

from backend.services.enrichment_service import (
    EnrichmentService,
    company_name_matches,
    is_directory_url,
)


class FakeSearch:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def search(self, query, limit=20):
        self.calls.append(query)
        return self.results


class FakeCrawler:
    def crawl(self, website, industry=None, source_keyword=None, address=None):
        return {
            "CompanyName": "Acme Logistics",
            "Email": "info@acme.com",
            "Phone": "+91 98123 45678",
            "LinkedInURL": "https://linkedin.com/company/acme",
            "CitiesServed": "Mumbai, Pune",
            "Notes": "Source keyword: x",
        }

    def fetch(self, url):
        return "<html>contact us info@acme.com +91 98123 45678</html>"


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}  {label}")
    return condition


ok = True
ok &= check("company_name_matches ignores legal suffix",
            company_name_matches("Acme Logistics Pvt Ltd", "Acme Logistics"))
ok &= check("directory urls rejected", is_directory_url("https://justdial.com/x"))

# Case 1: no website on the card -> Google finds the site -> crawl fills the rest.
svc = EnrichmentService(crawler=FakeCrawler(), web_search=FakeSearch([
    {"title": "Acme Logistics | Courier", "url": "https://acmelogistics.in/", "snippet": "Mumbai couriers"},
    {"title": "Acme on Justdial", "url": "https://justdial.com/acme", "snippet": "listing"},
    {"title": "Acme LinkedIn", "url": "https://linkedin.com/company/acme", "snippet": "li"},
]))
lead = svc.enrich({"CompanyName": "Acme Logistics", "Location": "Mumbai"}, industry="couriers")
ok &= check("case1 picked own site, not directory/social",
            lead["Website"] == "https://acmelogistics.in/")
ok &= check("case1 filled email", lead["Email"] == "info@acme.com")
ok &= check("case1 kept crawl phone", lead["Phone"] == "+91 98123 45678")
ok &= check("case1 marked useful", lead["IsUseful"] is True)
print("      queries tried:", svc.web_search.calls)
print("      notes:", lead["Notes"])

# Case 2: no website anywhere -> harvest the snippet, then the social profile.
svc2 = EnrichmentService(crawler=FakeCrawler(), web_search=FakeSearch([
    {"title": "Acme Logistics", "url": "https://facebook.com/acmelogistics",
     "snippet": "Call us on sales@acme.co.in or +91 99887 66554"},
    {"title": "Acme LinkedIn", "url": "https://linkedin.com/company/acmelog", "snippet": "co"},
]))
lead2 = svc2.enrich({"CompanyName": "Acme Logistics", "Location": "Mumbai"})
ok &= check("case2 email from snippet", lead2["Email"] == "sales@acme.co.in")
ok &= check("case2 phone from snippet", bool(lead2["Phone"]))
ok &= check("case2 linkedin kept", lead2["LinkedInURL"].endswith("acmelog"))
print("      notes:", lead2["Notes"])

# Case 3: nothing usable anywhere.
svc3 = EnrichmentService(crawler=FakeCrawler(), web_search=FakeSearch([]))
lead3 = svc3.enrich({"CompanyName": "Nameless Co"})
ok &= check("case3 flagged unusable", lead3["IsUseful"] is False)

# Case 4: card already has a website AND a phone -> no Google search at all.
svc4 = EnrichmentService(crawler=FakeCrawler(), web_search=FakeSearch([]))
lead4 = svc4.enrich({"CompanyName": "Acme Logistics", "Website": "https://acmelogistics.in/",
                     "Phone": "+91 98123 45678"})
ok &= check("case4 skipped google lookup", svc4.web_search.calls == [])
ok &= check("case4 still crawled", lead4["Email"] == "info@acme.com")

print("\nALL PASS" if ok else "\nSOME CHECKS FAILED")
raise SystemExit(0 if ok else 1)