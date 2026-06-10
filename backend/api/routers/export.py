import io
from fastapi import APIRouter, Response
import pandas as pd
from backend.services.lead_service import LeadService

router = APIRouter()

EXPORT_FIELDS = [
    "CompanyName",
    "Website",
    "Industry",
    "Email",
    "Phone",
    "LinkedIn",
    "ContactPage",
    "HasTestimonials",
    "HasVideoTestimonials",
    "HasCaseStudies",
    "HasGoogleReviews",
    "LeadScore",
    "Priority",
]


def build_export_dataframe(leads):
    rows = []
    for lead in leads:
        rows.append({field: lead.get(field) for field in EXPORT_FIELDS})
    return pd.DataFrame(rows)


@router.get("/export/csv")
def export_csv():
    leads = LeadService().list_leads(limit=10000)
    df = build_export_dataframe(leads)
    content = df.to_csv(index=False)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=clientalio_leads.csv"},
    )


@router.get("/export/excel")
def export_excel():
    leads = LeadService().list_leads(limit=10000)
    df = build_export_dataframe(leads)
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)
    return Response(
        content=buffer.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=clientalio_leads.xlsx"},
    )
