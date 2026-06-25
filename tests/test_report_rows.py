from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pdf_report import build_report_rows
from tests.test_pdf_smoke import SAMPLE_PAYLOAD


def test_manual_facility_name_override_is_used_only_in_report_body():
    payload = dict(SAMPLE_PAYLOAD)
    payload["manual"] = dict(SAMPLE_PAYLOAD["manual"], facilityNameOverride="Internal Local Facility Name")

    rows = build_report_rows(payload)

    assert rows[0] == ("Name of Facility", "Internal Local Facility Name", "base")
    assert all("INFINITE" not in value for _, value, _ in rows)


def test_report_contains_13_base_rows_and_12_metric_rows():
    rows = build_report_rows(SAMPLE_PAYLOAD)
    base_rows = [row for row in rows if row[2] == "base"]
    metric_rows = [row for row in rows if row[2] == "metric"]

    assert len(base_rows) == 13
    assert len(metric_rows) == 12
