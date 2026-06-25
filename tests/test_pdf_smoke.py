from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pdf_report import generate_snapshot_pdf

SAMPLE_PAYLOAD = {
    "ccn": "686123",
    "state": "FL",
    "provider": {
        "officialName": "Kendall Lakes Healthcare and Rehab Center",
        "location": "5280 SW 157th Ave, Miami, FL",
        "censusCapacity": "120",
        "ratings": {
            "overall": "1",
            "healthInspection": "1",
            "staffing": "2",
            "qualityResidentCare": "4",
        },
    },
    "manual": {
        "facilityNameOverride": "",
        "emr": "PCC",
        "currentCensus": "112",
        "patientType": "Long-term & Short-term",
        "previousCoverage": "Yes",
        "previousProviderPerformance": "About 30 patients/day",
        "medicalCoverage": "Optometry, PCP, Podiatry",
    },
    "metrics": [
        {"label": "Short Term Hospitalization", "value": "18.7%"},
        {"label": "STR National Avg. for Hospitalization", "value": "21.5%"},
        {"label": "STR State National Avg. for Hospitalization", "value": "23.8%"},
        {"label": "STR ED Visit", "value": "13.9%"},
        {"label": "STR ED Visits National Avg.", "value": "11.6%"},
        {"label": "STR ED Visits State Avg.", "value": "9.3%"},
        {"label": "LT Hospitalization", "value": "1.86"},
        {"label": "LT National Avg. for Hospitalization", "value": "1.65"},
        {"label": "LT State National Avg. for Hospitalization", "value": "1.95"},
        {"label": "ED Visit", "value": "6.94"},
        {"label": "LT ED Visits National Avg.", "value": "1.65"},
        {"label": "LT ED Visits State Avg.", "value": "1.21"},
    ],
    "careCompareUrl": "https://www.medicare.gov/care-compare/details/nursing-home/686123/view-all?state=FL",
}


def test_pdf_smoke(tmp_path):
    pdf = generate_snapshot_pdf(SAMPLE_PAYLOAD)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000
    output = tmp_path / "sample.pdf"
    output.write_bytes(pdf)
    assert output.exists()


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "sample_kendall_lakes_snapshot.pdf"
    out.write_bytes(generate_snapshot_pdf(SAMPLE_PAYLOAD))
    print(out)
