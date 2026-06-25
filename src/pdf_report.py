from __future__ import annotations

import io
import re
import html
from typing import Any, Dict, List, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

BRAND_LINE = "INFINITE — Managed by MEDELITE"
REPORT_TITLE = "FACILITY ASSESSMENT SNAPSHOT"

BASE_ROWS = [
    ("Name of Facility", "facilityName", "base"),
    ("Location", "location", "base"),
    ("EMR", "emr", "base"),
    ("Census Capacity", "censusCapacity", "base"),
    ("Current Census", "currentCensus", "base"),
    ("Type of Patient", "patientType", "base"),
    ("Previous Coverage from Medelite", "previousCoverage", "base"),
    ("Previous Provider Performance from Medelite", "previousProviderPerformance", "base"),
    ("Medical Coverage", "medicalCoverage", "base"),
    ("Overall Star Rating", "overallRating", "base"),
    ("Health Inspection", "healthInspection", "base"),
    ("Staffing", "staffing", "base"),
    ("Quality of Resident Care", "qualityResidentCare", "base"),
]


def _clean(value: Any) -> str:
    if value is None:
        return "N/A"
    text = str(value).strip()
    return text if text else "N/A"


def sanitize_filename(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return safe.strip("_") or "facility_snapshot"


def build_report_rows(payload: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    provider = payload.get("provider", {}) or {}
    manual = payload.get("manual", {}) or {}
    ratings = provider.get("ratings", {}) or {}

    facility_name = _clean(manual.get("facilityNameOverride") or provider.get("officialName"))
    row_values = {
        "facilityName": facility_name,
        "location": provider.get("location"),
        "emr": manual.get("emr"),
        "censusCapacity": provider.get("censusCapacity"),
        "currentCensus": manual.get("currentCensus"),
        "patientType": manual.get("patientType"),
        "previousCoverage": manual.get("previousCoverage"),
        "previousProviderPerformance": manual.get("previousProviderPerformance"),
        "medicalCoverage": manual.get("medicalCoverage"),
        "overallRating": ratings.get("overall"),
        "healthInspection": ratings.get("healthInspection"),
        "staffing": ratings.get("staffing"),
        "qualityResidentCare": ratings.get("qualityResidentCare"),
    }

    rows: List[Tuple[str, str, str]] = [(label, _clean(row_values.get(key)), kind) for label, key, kind in BASE_ROWS]
    for metric in payload.get("metrics", []) or []:
        rows.append((_clean(metric.get("label")), _clean(metric.get("value")), "metric"))
    return rows


def _brand_paragraph() -> Paragraph:
    # The visible text is exactly the required phrase, with styling on each part.
    return Paragraph(
        '<font color="#ec00c8" size="28"><b>INFINITE</b></font>'
        '<font color="#333333" size="22"><b> — </b></font>'
        '<font color="#2584b8" size="14"><b>Managed by</b></font>'
        '<font color="#6b6f76" size="14"><b> MEDELITE</b></font>',
        ParagraphStyle(name="Brand", alignment=TA_CENTER, leading=30),
    )


def _center_paragraph(text: str, size: int = 14, bold: bool = False) -> Paragraph:
    content = f"<b>{text}</b>" if bold else text
    return Paragraph(content, ParagraphStyle(name=f"Center{size}{bold}", alignment=TA_CENTER, fontName="Helvetica", fontSize=size, leading=size + 2))


def generate_snapshot_pdf(payload: Dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.72 * inch,
        rightMargin=0.72 * inch,
        topMargin=0.48 * inch,
        bottomMargin=0.42 * inch,
        title="Facility Assessment Snapshot",
        author="INFINITE Managed by MEDELITE",
    )

    state = _clean(payload.get("state") or (payload.get("provider", {}) or {}).get("state"))
    ccn = _clean(payload.get("ccn"))
    care_compare_url = _clean(payload.get("careCompareUrl"))

    story: List[Any] = []
    story.append(_brand_paragraph())
    story.append(Spacer(1, 0.05 * inch))
    story.append(_center_paragraph(REPORT_TITLE, size=13, bold=True))
    story.append(_center_paragraph(state, size=12, bold=True))
    story.append(Spacer(1, 0.04 * inch))

    rows = build_report_rows(payload)
    table_data = [[Paragraph(f"<b>{html.escape(label)}</b>", ParagraphStyle(name=f"Label{i}", fontName="Helvetica-Bold", fontSize=9.5, leading=11)),
                   Paragraph(html.escape(value), ParagraphStyle(name=f"Value{i}", fontName="Helvetica-Oblique", fontSize=9.5, leading=11))]
                  for i, (label, value, _kind) in enumerate(rows)]

    table = Table(table_data, colWidths=[3.55 * inch, 3.05 * inch], repeatRows=0)
    style_commands: List[Tuple[Any, ...]] = [
        ("GRID", (0, 0), (-1, -1), 1.0, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
    ]
    # The reference planning document highlighted metric labels in yellow, but
    # the production export intentionally uses a clean white table throughout.
    table.setStyle(TableStyle(style_commands))
    story.append(table)
    story.append(Spacer(1, 0.08 * inch))

    # Use a small, clickable hyperlink. It is intentionally outside the table so the
    # whole report body remains aligned to the reference snapshot.
    story.append(Paragraph(
        f'<font size="8">CMS source profile for CCN {ccn}: </font>'
        f'<a href="{html.escape(care_compare_url, quote=True)}"><font color="#0645AD" size="8"><u>{html.escape(care_compare_url)}</u></font></a>',
        ParagraphStyle(name="SourceLink", fontName="Helvetica", fontSize=8, leading=9),
    ))

    doc.build(story)
    return buffer.getvalue()
