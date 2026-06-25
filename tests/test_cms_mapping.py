from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cms_client import build_metric_rows, pdc_query_url, provider_report_fields


def test_provider_report_fields_maps_cms_dictionary_names():
    provider = {
        "CMS Certification Number (CCN)": "686123",
        "Provider Name": "Kendall Lakes Healthcare and Rehab Center",
        "Provider Address": "5280 SW 157th Ave",
        "City/Town": "Miami",
        "State": "FL",
        "Number of Certified Beds": "120",
        "Overall Rating": "1",
        "Health Inspection Rating": "1",
        "Staffing Rating": "2",
        "QM Rating": "4",
    }

    fields = provider_report_fields(provider)

    assert fields["ccn"] == "686123"
    assert fields["officialName"] == "Kendall Lakes Healthcare and Rehab Center"
    assert fields["location"] == "5280 SW 157th Ave, Miami, FL"
    assert fields["censusCapacity"] == "120"
    assert fields["ratings"] == {
        "overall": "1",
        "healthInspection": "1",
        "staffing": "2",
        "qualityResidentCare": "4",
    }


def test_build_metric_rows_outputs_all_12_required_rows():
    claims = [
        {"Measure Code": "521", "Measure Description": "Short-stay residents rehospitalized", "Resident Type": "Short-Stay", "Adjusted Score": "18.7"},
        {"Measure Code": "522", "Measure Description": "Short-stay residents with an outpatient emergency department visit", "Resident Type": "Short-Stay", "Adjusted Score": "13.9"},
        {"Measure Code": "551", "Measure Description": "Long-stay resident hospitalization rate", "Resident Type": "Long-Stay", "Adjusted Score": "1.86"},
        {"Measure Code": "552", "Measure Description": "Long-stay resident outpatient emergency department visit rate", "Resident Type": "Long-Stay", "Adjusted Score": "6.94"},
    ]
    national = [
        {"State or Nation": "NATION", "Measure Code": "521", "Measure Description": "Short-stay residents rehospitalized", "Average": "21.5"},
        {"State or Nation": "NATION", "Measure Code": "522", "Measure Description": "Short-stay residents with an outpatient emergency department visit", "Average": "11.6"},
        {"State or Nation": "NATION", "Measure Code": "551", "Measure Description": "Long-stay resident hospitalization rate", "Average": "1.65"},
        {"State or Nation": "NATION", "Measure Code": "552", "Measure Description": "Long-stay resident outpatient emergency department visit rate", "Average": "1.65"},
    ]
    state = [
        {"State or Nation": "FL", "Measure Code": "521", "Measure Description": "Short-stay residents rehospitalized", "Average": "23.8"},
        {"State or Nation": "FL", "Measure Code": "522", "Measure Description": "Short-stay residents with an outpatient emergency department visit", "Average": "9.3"},
        {"State or Nation": "FL", "Measure Code": "551", "Measure Description": "Long-stay resident hospitalization rate", "Average": "1.95"},
        {"State or Nation": "FL", "Measure Code": "552", "Measure Description": "Long-stay resident outpatient emergency department visit rate", "Average": "1.21"},
    ]

    rows = build_metric_rows(claims, state, national)

    assert len(rows) == 12
    assert rows[0] == {"label": "Short Term Hospitalization", "value": "18.7%", "kind": "metric"}
    assert rows[1] == {"label": "STR National Avg. for Hospitalization", "value": "21.5%", "kind": "metric"}
    assert rows[2] == {"label": "STR State National Avg. for Hospitalization", "value": "23.8%", "kind": "metric"}
    assert rows[-1] == {"label": "LT ED Visits State Avg.", "value": "1.21", "kind": "metric"}


def test_pdc_query_url_uses_stable_dataset_id_and_ccn_condition():
    url = pdc_query_url("4pq5-n9py", conditions=[("cms_certification_number_ccn", "=", "686123")], limit=10)

    assert "data.cms.gov/provider-data/api/1/datastore/query/4pq5-n9py/0" in url
    assert "conditions[0][property]=cms_certification_number_ccn" in url
    assert "conditions[0][operator]=%3D" in url
    assert "conditions[0][value]=686123" in url
