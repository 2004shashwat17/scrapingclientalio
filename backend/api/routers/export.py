import io
from fastapi import APIRouter, Response
import pandas as pd
from backend.services.lead_service import LeadService

router = APIRouter()

EXPORT_FIELDS = {
    "Company Name": "CompanyName",
    "Website": "Website",
    "Headquarters": "Headquarters",
    "Cities Served": "CitiesServed",
    "Industry": "Industry",
    "Fleet Size (if public)": "FleetSizePublic",
    "Employees": "Employees",
    "Revenue (if public)": "RevenuePublic",
    "Decision Makers": "DecisionMakers",
    "LinkedIn URL": "LinkedInURL",
    "Email": "Email",
    "Phone": "Phone",
    "CRM/TMS Used (if public)": "CRMTMSUsedPublic",
    "Delivery Volume (if public)": "DeliveryVolumePublic",
    "Existing POD Solution": "ExistingPODSolution",
    "Notes": "Notes",
}


def build_export_dataframe(leads):
    rows = []
    for lead in leads:
        rows.append({label: lead.get(field) for label, field in EXPORT_FIELDS.items()})
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
