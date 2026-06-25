from __future__ import annotations

import json
import math
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Provider Data Catalog (PDC) datasets use short stable dataset IDs in this API.
# The final "/0" is the distribution index. PDC currently exposes one resource per
# dataset, so index 0 is stable across data refreshes.
CMS_PDC_QUERY_BASE = "https://data.cms.gov/provider-data/api/1/datastore/query"

DATASETS = {
    "provider_info": "4pq5-n9py",
    "claims_qm": "ijh5-nb2v",
    "state_averages": "xcdc-v8bm",
}

# PDC API property names are machine-safe snake_case versions of the dictionary
# headers. row_get below also accepts human-readable dictionary names so that the
# rest of the app remains easy to read.
CCN_PROPERTY = "cms_certification_number_ccn"
STATE_AVG_PROPERTY = "state_or_nation"

MISSING_VALUES = {
    "", "nan", "none", "null", "n/a", "na", "not available", "data not available",
    "not applicable", "not enough data", "suppressed", "--", "-", "*",
}


class CmsApiError(RuntimeError):
    """Raised when CMS is reachable but the query cannot be completed."""


def normalize_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())).strip()


def clean_string(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in MISSING_VALUES:
        return ""
    return text


def row_get(row: Dict[str, Any], *aliases: str) -> str:
    """Return a CMS row value using either API property or dictionary label aliases."""
    if not row:
        return ""
    normalized = {normalize_key(k): v for k, v in row.items()}
    for alias in aliases:
        key = normalize_key(alias)
        if key in normalized:
            return clean_string(normalized[key])
    return ""


def parse_number(value: Any) -> Optional[float]:
    text = clean_string(value).replace(",", "").replace("%", "")
    if not text:
        return None
    try:
        number = float(text)
        if math.isnan(number) or math.isinf(number):
            return None
        return number
    except ValueError:
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            return None
        try:
            return float(match.group(0))
        except ValueError:
            return None


def format_value(value: Any, kind: str = "plain") -> str:
    text = clean_string(value)
    number = parse_number(text)
    if number is None:
        return text or "N/A"

    if kind == "percent":
        # CMS percentages can arrive either as 18.7 or 0.187 depending on table/source.
        if 0 < abs(number) <= 1:
            number *= 100
        return f"{number:.1f}%"
    if kind == "rate":
        return f"{number:.2f}"
    if kind == "integer":
        return str(int(round(number)))
    if number.is_integer():
        return str(int(number))
    return f"{number:g}"


@dataclass(frozen=True)
class MetricDefinition:
    key: str
    report_label: str
    resident_type: str
    measure_codes: Tuple[str, ...]
    description_keywords: Tuple[str, ...]
    excluded_keywords: Tuple[str, ...]
    format_kind: str


METRIC_DEFINITIONS: Tuple[MetricDefinition, ...] = (
    MetricDefinition(
        key="str_hospitalization",
        report_label="Short Term Hospitalization",
        resident_type="short",
        measure_codes=("521", "QM521"),
        description_keywords=("short", "rehospital", "hospital", "admission"),
        excluded_keywords=("emergency", "ed visit", "outpatient emergency"),
        format_kind="percent",
    ),
    MetricDefinition(
        key="str_ed_visit",
        report_label="STR ED Visit",
        resident_type="short",
        measure_codes=("522", "QM522"),
        description_keywords=("short", "emergency", "department", "outpatient"),
        excluded_keywords=("rehospital",),
        format_kind="percent",
    ),
    MetricDefinition(
        key="lt_hospitalization",
        report_label="LT Hospitalization",
        resident_type="long",
        measure_codes=("551", "QM551"),
        description_keywords=("long", "hospital", "hospitalization"),
        excluded_keywords=("emergency", "ed visit", "outpatient emergency"),
        format_kind="rate",
    ),
    MetricDefinition(
        key="lt_ed_visit",
        report_label="ED Visit",
        resident_type="long",
        measure_codes=("552", "QM552"),
        description_keywords=("long", "emergency", "department", "outpatient"),
        excluded_keywords=("rehospital",),
        format_kind="rate",
    ),
)

AVG_REPORT_LABELS = {
    "str_hospitalization": ("STR National Avg. for Hospitalization", "STR State National Avg. for Hospitalization"),
    "str_ed_visit": ("STR ED Visits National Avg.", "STR ED Visits State Avg."),
    "lt_hospitalization": ("LT National Avg. for Hospitalization", "LT State National Avg. for Hospitalization"),
    "lt_ed_visit": ("LT ED Visits National Avg.", "LT ED Visits State Avg."),
}


def _request_json(url: str, timeout: int = 25) -> List[Dict[str, Any]]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "MedeliteFacilityAssessment/1.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except Exception as exc:  # urllib raises several network/HTTP subclasses.
        raise CmsApiError(f"CMS API request failed: {exc}") from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise CmsApiError("CMS API returned non-JSON data.") from exc

    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        rows = data.get("results") or data.get("data") or []
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def pdc_query_url(
    dataset_id: str,
    *,
    conditions: Optional[Sequence[Tuple[str, str, str]]] = None,
    limit: int = 100,
    offset: int = 0,
    properties: Optional[Sequence[str]] = None,
) -> str:
    params: Dict[str, Any] = {
        "limit": str(limit),
        "offset": str(offset),
        "format": "json",
    }
    if properties:
        params["properties[]"] = list(properties)
    for index, (property_name, operator, value) in enumerate(conditions or []):
        params[f"conditions[{index}][property]"] = property_name
        params[f"conditions[{index}][operator]"] = operator
        params[f"conditions[{index}][value]"] = value
    query = urllib.parse.urlencode(params, doseq=True, safe="[]")
    return f"{CMS_PDC_QUERY_BASE}/{dataset_id}/0?{query}"


def query_pdc(
    dataset_id: str,
    *,
    conditions: Optional[Sequence[Tuple[str, str, str]]] = None,
    limit: int = 100,
    offset: int = 0,
    properties: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    return _request_json(pdc_query_url(dataset_id, conditions=conditions, limit=limit, offset=offset, properties=properties))


def query_by_property(dataset_id: str, property_name: str, value: str, aliases: Sequence[str], limit: int = 100) -> List[Dict[str, Any]]:
    rows = query_pdc(dataset_id, conditions=[(property_name, "=", value)], limit=limit)
    expected = normalize_text(value)
    filtered = [row for row in rows if any(normalize_text(row_get(row, alias)) == expected for alias in aliases)]
    return filtered or rows


def fetch_provider(ccn: str) -> Dict[str, Any]:
    rows = query_by_property(
        DATASETS["provider_info"],
        CCN_PROPERTY,
        ccn,
        aliases=(CCN_PROPERTY, "CMS Certification Number (CCN)", "Provider CCN", "Federal Provider Number", "PROVNUM"),
        limit=10,
    )
    if not rows:
        raise LookupError(f"No active nursing home provider found for CCN {ccn}.")
    return rows[0]


def fetch_claims(ccn: str) -> List[Dict[str, Any]]:
    return query_by_property(
        DATASETS["claims_qm"],
        CCN_PROPERTY,
        ccn,
        aliases=(CCN_PROPERTY, "CMS Certification Number (CCN)", "Provider CCN", "Federal Provider Number", "PROVNUM"),
        limit=100,
    )


def fetch_state_average_rows(state_or_nation: str) -> List[Dict[str, Any]]:
    return query_by_property(
        DATASETS["state_averages"],
        STATE_AVG_PROPERTY,
        state_or_nation,
        aliases=(STATE_AVG_PROPERTY, "State or Nation", "State", "Nation"),
        limit=25,
    )


def best_claims_row(rows: Sequence[Dict[str, Any]], metric: MetricDefinition) -> Optional[Dict[str, Any]]:
    best: Tuple[int, Optional[Dict[str, Any]]] = (-1, None)
    for row in rows:
        description = normalize_text(row_get(row, "measure_description", "Measure Description", "Measure", "Quality Measure Description"))
        resident_type = normalize_text(row_get(row, "resident_type", "Resident type", "Resident Type"))
        raw_code = row_get(row, "measure_code", "Measure Code", "Measure ID", "Quality Measure Code")
        code = normalize_text(raw_code).replace("qm", "")

        haystack = f"{description} {resident_type} {code}"
        score = 0
        if code in {normalize_text(c).replace("qm", "") for c in metric.measure_codes}:
            score += 120
        if metric.resident_type and metric.resident_type in resident_type:
            score += 35
        for keyword in metric.description_keywords:
            if normalize_text(keyword) in haystack:
                score += 12
        for keyword in metric.excluded_keywords:
            if normalize_text(keyword) in haystack:
                score -= 50
        if parse_number(row_get(row, "adjusted_score", "Adjusted Score", "risk_adjusted_score", "Risk-Adjusted Score")) is None:
            score -= 15

        if score > best[0]:
            best = (score, row)

    return best[1] if best[0] >= 45 else None


def metric_score_from_claims(rows: Sequence[Dict[str, Any]], metric: MetricDefinition) -> str:
    row = best_claims_row(rows, metric)
    if not row:
        return "N/A"
    value = row_get(row, "adjusted_score", "Adjusted Score", "risk_adjusted_score", "Risk-Adjusted Score", "score", "Score", "observed_score", "Observed Score")
    return format_value(value, metric.format_kind)


def _metric_code_tokens(metric: MetricDefinition) -> Tuple[str, ...]:
    return tuple(normalize_text(code).replace("qm", "") for code in metric.measure_codes)


def _candidate_average_fields(row: Dict[str, Any], metric: MetricDefinition) -> List[Tuple[int, Any]]:
    candidates: List[Tuple[int, Any]] = []
    code_tokens = _metric_code_tokens(metric)
    for key, value in row.items():
        key_norm = normalize_text(key)
        key_compact = normalize_key(key)
        if not key_norm or any(term in key_norm for term in ("footnote", "state or nation", "processing date")):
            continue
        if parse_number(value) is None:
            continue

        score = 0
        if any(token and (f"qm{token}" in key_compact or key_compact.endswith(token)) for token in code_tokens):
            score += 90
        if metric.resident_type in key_norm:
            score += 25
        for keyword in metric.description_keywords:
            kw = normalize_text(keyword)
            if kw in key_norm:
                score += 12
        for keyword in metric.excluded_keywords:
            if normalize_text(keyword) in key_norm:
                score -= 50
        if score >= 35:
            candidates.append((score, value))
    return sorted(candidates, key=lambda item: item[0], reverse=True)


def _average_from_long_rows(rows: Sequence[Dict[str, Any]], metric: MetricDefinition) -> Optional[Any]:
    best: Tuple[int, Any] = (-1, None)
    value_aliases = ("average", "Average", "state_average", "State Average", "national_average", "National Average", "value", "Value", "adjusted_score", "Adjusted Score", "score", "Score")
    measure_aliases = ("measure_description", "Measure Description", "measure", "Measure", "measure_name", "Measure Name", "measure_code", "Measure Code")
    code_tokens = _metric_code_tokens(metric)
    for row in rows:
        haystack = " ".join(normalize_text(row_get(row, alias)) for alias in measure_aliases)
        if not haystack:
            continue
        score = 0
        if any(token and token in haystack for token in code_tokens):
            score += 90
        if metric.resident_type in haystack:
            score += 20
        for keyword in metric.description_keywords:
            if normalize_text(keyword) in haystack:
                score += 12
        for keyword in metric.excluded_keywords:
            if normalize_text(keyword) in haystack:
                score -= 50
        value = ""
        for alias in value_aliases:
            value = row_get(row, alias)
            if value:
                break
        if score > best[0] and value:
            best = (score, value)
    return best[1] if best[0] >= 35 else None


def metric_average(rows: Sequence[Dict[str, Any]], metric: MetricDefinition) -> str:
    if not rows:
        return "N/A"

    # Some CMS average tables are long; the Nursing Home State/US Averages table is wide.
    long_value = _average_from_long_rows(rows, metric)
    if long_value is not None:
        return format_value(long_value, metric.format_kind)

    wide_candidates: List[Tuple[int, Any]] = []
    for row in rows:
        wide_candidates.extend(_candidate_average_fields(row, metric))
    if not wide_candidates:
        return "N/A"
    return format_value(wide_candidates[0][1], metric.format_kind)


def build_location(provider: Dict[str, Any]) -> str:
    explicit = row_get(provider, "location", "Location")
    if explicit:
        return re.sub(r"\s+", " ", explicit).strip()
    parts = [
        row_get(provider, "provider_address", "Provider Address", "Address"),
        row_get(provider, "citytown", "city_town", "City/Town", "City"),
        row_get(provider, "state", "State"),
    ]
    return ", ".join([p for p in parts if p])


def provider_report_fields(provider: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ccn": row_get(provider, CCN_PROPERTY, "CMS Certification Number (CCN)", "Provider CCN", "PROVNUM"),
        "officialName": row_get(provider, "provider_name", "Provider Name", "legal_business_name", "Legal Business Name", "Facility Name"),
        "location": build_location(provider),
        "state": row_get(provider, "state", "State"),
        "censusCapacity": format_value(row_get(provider, "number_of_certified_beds", "Number of Certified Beds"), "integer"),
        "averageResidentsPerDay": format_value(row_get(provider, "average_number_of_residents_per_day", "Average Number of Residents per Day"), "plain"),
        "ratings": {
            "overall": format_value(row_get(provider, "overall_rating", "Overall Rating"), "integer"),
            "healthInspection": format_value(row_get(provider, "health_inspection_rating", "Health Inspection Rating"), "integer"),
            "staffing": format_value(row_get(provider, "staffing_rating", "Staffing Rating"), "integer"),
            "qualityResidentCare": format_value(row_get(provider, "qm_rating", "QM Rating", "Quality Measure Rating"), "integer"),
        },
    }


def build_metric_rows(claims: Sequence[Dict[str, Any]], state_rows: Sequence[Dict[str, Any]], national_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for metric in METRIC_DEFINITIONS:
        facility_value = metric_score_from_claims(claims, metric)
        national_value = metric_average(national_rows, metric)
        state_value = metric_average(state_rows, metric)
        national_label, state_label = AVG_REPORT_LABELS[metric.key]
        rows.append({"label": metric.report_label, "value": facility_value, "kind": "metric"})
        rows.append({"label": national_label, "value": national_value, "kind": "metric"})
        rows.append({"label": state_label, "value": state_value, "kind": "metric"})
    return rows


def get_facility_snapshot(ccn: str) -> Dict[str, Any]:
    ccn = re.sub(r"\D", "", ccn or "")
    if not re.fullmatch(r"\d{6}", ccn):
        raise ValueError("Please enter a valid 6-digit CMS Certification Number (CCN).")

    provider = fetch_provider(ccn)
    provider_fields = provider_report_fields(provider)
    claims_rows = fetch_claims(ccn)
    state = provider_fields.get("state") or row_get(provider, "state", "State")
    state_rows = fetch_state_average_rows(state) if state else []
    national_rows = fetch_state_average_rows("NATION")
    metric_rows = build_metric_rows(claims_rows, state_rows, national_rows)

    state_query = urllib.parse.quote(str(state or ""))
    return {
        "ccn": ccn,
        "state": state,
        "provider": provider_fields,
        "metrics": metric_rows,
        "careCompareUrl": f"https://www.medicare.gov/care-compare/details/nursing-home/{ccn}/view-all?state={state_query}",
        "sourceDatasetIds": DATASETS,
    }
