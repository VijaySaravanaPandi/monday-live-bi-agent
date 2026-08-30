"""
Data Normalization / Resilience Layer
---------------------------------------
Takes raw monday.com item data (from monday_client.py) and produces
clean, consistent Python dicts ready for the BI engine.

Responsibilities:
- Handle missing/null values gracefully (never crash on absence)
- Normalize inconsistent date formats
- Normalize numeric/currency fields (strip symbols, commas)
- Normalize naming conventions (sector labels, status labels)
- Record every issue encountered into a DataQualityReport

This module NEVER discards an item just because a field is messy —
it does its best, flags the issue, and moves on. That's the
"provide meaningful results even with incomplete data" requirement.
"""

import re
from datetime import datetime
from dateutil import parser as date_parser
from typing import Optional, Dict, Any, List

from src.data_quality import DataQualityReport


# Canonical sector names. Raw monday.com data may contain variants
# like "mining ", "MINING", "Mining Sector" — we map them to one
# consistent label so BI queries like "energy sector" work reliably.
SECTOR_CANONICAL_MAP = {
    "mining": "Mining",
    "railways": "Railways",
    "railway": "Railways",
    "renewables": "Renewables",
    "renewable energy": "Renewables",
    "energy": "Energy",
    "powerline": "Powerline",
    "power line": "Powerline",
    "power": "Energy",
    "oil and gas": "Oil & Gas",
    "oil & gas": "Oil & Gas",
    "others": "Others",
    "other": "Others",
}


def normalize_text(value: Optional[str]) -> Optional[str]:
    """Trim whitespace, collapse internal spaces, return None for empty/null."""
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    return cleaned if cleaned else None


def normalize_sector(raw_value: Optional[str], report: Optional[DataQualityReport] = None) -> Optional[str]:
    """Maps messy sector text to a canonical label."""
    cleaned = normalize_text(raw_value)
    if cleaned is None:
        return None

    key = cleaned.lower().strip()
    if key in SECTOR_CANONICAL_MAP:
        return SECTOR_CANONICAL_MAP[key]

    # Not in our known map — keep the cleaned original but flag it,
    # so the BI layer can still use it, and the user can be told
    # it's an unrecognized/uncanonicalized label.
    if report:
        report.record_unrecognized_sector(cleaned)
    return cleaned


def normalize_date(raw_value: Optional[str], report: Optional[DataQualityReport] = None) -> Optional[str]:
    """
    Parses inconsistent date strings (e.g. '2026-02-26', '26/02/2026',
    'Feb 26, 2026') into a single canonical ISO format: YYYY-MM-DD.
    Returns None if the value is missing or unparseable (and logs it).
    """
    cleaned = normalize_text(raw_value)
    if cleaned is None:
        return None

    try:
        parsed = date_parser.parse(cleaned, dayfirst=False, fuzzy=True)
        return parsed.strftime("%Y-%m-%d")
    except (ValueError, OverflowError, TypeError):
        if report:
            report.record_malformed_date()
        return None


def normalize_number(raw_value: Optional[str], report: Optional[DataQualityReport] = None) -> Optional[float]:
    """
    Strips currency symbols, commas, and whitespace from numeric fields
    and returns a clean float. Returns None if unparseable.
    Examples handled: '489360', '4,89,360', '₹489360', ' 489360.0 '
    """
    cleaned = normalize_text(raw_value)
    if cleaned is None:
        return None

    # Strip anything that isn't a digit, minus sign, or decimal point
    stripped = re.sub(r"[^\d\.\-]", "", cleaned)

    if stripped in ("", "-", "."):
        if report:
            report.record_malformed_number()
        return None

    try:
        return float(stripped)
    except ValueError:
        if report:
            report.record_malformed_number()
        return None


def extract_column_map(item: Dict[str, Any]) -> Dict[str, str]:
    """
    Converts monday.com's raw column_values array (list of
    {id, text, value, column: {title, type}}) into a simple
    {column_title: text_value} dict for easier access.
    """
    result = {}
    for col in item.get("column_values", []):
        title = col.get("column", {}).get("title")
        text = col.get("text")
        if title:
            result[title] = text
    return result


def normalize_deal(item: Dict[str, Any], report: DataQualityReport) -> Dict[str, Any]:
    """Normalizes a single raw Deals board item into a clean dict."""
    cols = extract_column_map(item)
    report.total_items += 1

    required_fields = ["Deal Status", "Masked Deal value", "Sector/service"]
    missing_any = False
    for f in required_fields:
        if not normalize_text(cols.get(f)):
            report.record_missing_field(f)
            missing_any = True
    if missing_any:
        report.items_with_missing_fields += 1

    return {
        "id": item.get("id"),
        "deal_name": normalize_text(item.get("name")),
        "owner_code": normalize_text(cols.get("Owner code")),
        "client_code": normalize_text(cols.get("Client Code")),
        "status": normalize_text(cols.get("Deal Status")),
        "close_date_actual": normalize_date(cols.get("Close Date (A)"), report),
        "closure_probability": normalize_text(cols.get("Closure Probability")),
        "deal_value": normalize_number(cols.get("Masked Deal value"), report),
        "tentative_close_date": normalize_date(cols.get("Tentative Close Date"), report),
        "deal_stage": normalize_text(cols.get("Deal Stage")),
        "product": normalize_text(cols.get("Product deal")),
        "sector": normalize_sector(cols.get("Sector/service"), report),
        "created_date": normalize_date(cols.get("Created Date"), report),
    }


def normalize_work_order(item: Dict[str, Any], report: DataQualityReport) -> Dict[str, Any]:
    """Normalizes a single raw Work Orders board item into a clean dict."""
    cols = extract_column_map(item)
    report.total_items += 1

    required_fields = ["Execution Status", "Sector", "Amount in Rupees (Excl of GST) (Masked)"]
    missing_any = False
    for f in required_fields:
        if not normalize_text(cols.get(f)):
            report.record_missing_field(f)
            missing_any = True
    if missing_any:
        report.items_with_missing_fields += 1

    return {
        "id": item.get("id"),
        "work_order_id": normalize_text(item.get("name")),
        "deal_name_masked": normalize_text(cols.get("Deal name masked")),
        "customer_code": normalize_text(cols.get("Customer Name Code")),
        "nature_of_work": normalize_text(cols.get("Nature of Work")),
        "execution_status": normalize_text(cols.get("Execution Status")),
        "sector": normalize_sector(cols.get("Sector"), report),
        "type_of_work": normalize_text(cols.get("Type of Work")),
        "probable_start_date": normalize_date(cols.get("Probable Start Date"), report),
        "probable_end_date": normalize_date(cols.get("Probable End Date"), report),
        "amount_excl_gst": normalize_number(cols.get("Amount in Rupees (Excl of GST) (Masked)"), report),
        "amount_incl_gst": normalize_number(cols.get("Amount in Rupees (Incl of GST) (Masked)"), report),
        "billed_value_excl_gst": normalize_number(cols.get("Billed Value in Rupees (Excl of GST.) (Masked)"), report),
        "collected_amount_incl_gst": normalize_number(cols.get("Collected Amount in Rupees (Incl of GST.) (Masked)"), report),
        "amount_receivable": normalize_number(cols.get("Amount Receivable (Masked)"), report),
        "invoice_status": normalize_text(cols.get("Invoice Status")),
        "wo_status_billed": normalize_text(cols.get("WO Status (billed)")),
        "collection_status": normalize_text(cols.get("Collection status")),
        "collection_date": normalize_date(cols.get("Collection Date"), report),
        "billing_status": normalize_text(cols.get("Billing Status")),
    }


def normalize_deals_board(raw_items: List[Dict[str, Any]]) -> tuple:
    """Normalizes a full list of raw Deals items. Returns (clean_items, report)."""
    report = DataQualityReport(board_name="Deals")
    clean = [normalize_deal(item, report) for item in raw_items]
    return clean, report


def normalize_work_orders_board(raw_items: List[Dict[str, Any]]) -> tuple:
    """Normalizes a full list of raw Work Orders items. Returns (clean_items, report)."""
    report = DataQualityReport(board_name="Work Orders")
    clean = [normalize_work_order(item, report) for item in raw_items]
    return clean, report