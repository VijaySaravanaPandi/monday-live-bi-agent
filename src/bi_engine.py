"""
Deterministic BI Engine
-------------------------
Takes normalized Deals/Work Orders data (from normalizer.py) and
computes business metrics using plain, testable, deterministic code.

CRITICAL DESIGN RULE: the LLM never performs arithmetic. It only ever
receives the outputs of these functions. This guarantees numbers shown
to the founder are always correct, regardless of what the LLM "thinks"
the math should be.

All functions accept an optional `filters` dict so the orchestrator
(Phase 4/5) can slice data by sector, stage, status, date range, etc.
without duplicating filtering logic everywhere.
"""

from typing import List, Dict, Any, Optional
from collections import defaultdict


def _matches_filters(record: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:
    """
    Generic filter matcher. filters = {"sector": "Mining", "status": "Open"}
    Matching is case-insensitive on string fields. A filter key not
    present in the record, or a None value, is treated as "no match"
    (fails closed, not silently ignored) — except when the record's
    field itself is None, in which case it's excluded (can't confirm
    a match against missing data).
    """
    if not filters:
        return True

    for key, expected in filters.items():
        if expected is None:
            continue
        actual = record.get(key)
        if actual is None:
            return False
        if isinstance(actual, str) and isinstance(expected, str):
            if actual.strip().lower() != expected.strip().lower():
                return False
        else:
            if actual != expected:
                return False
    return True


def _apply_filters(records: List[Dict[str, Any]], filters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [r for r in records if _matches_filters(r, filters)]


# ---------------------------------------------------------------------
# DEALS METRICS
# ---------------------------------------------------------------------

def total_pipeline_value(deals: List[Dict[str, Any]], filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Sum of deal_value across matching deals. Skips deals with no value (doesn't assume 0)."""
    matched = _apply_filters(deals, filters)
    valued = [d for d in matched if d.get("deal_value") is not None]

    total = sum(d["deal_value"] for d in valued)

    return {
        "metric": "total_pipeline_value",
        "value": round(total, 2),
        "deal_count": len(matched),
        "deals_with_valid_value": len(valued),
        "deals_missing_value": len(matched) - len(valued),
        "filters_applied": filters or {},
    }


def deal_count_by_stage(deals: List[Dict[str, Any]], filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Count of deals grouped by deal_stage."""
    matched = _apply_filters(deals, filters)
    counts = defaultdict(int)
    for d in matched:
        stage = d.get("deal_stage") or "Unknown"
        counts[stage] += 1

    return {
        "metric": "deal_count_by_stage",
        "breakdown": dict(counts),
        "total_deals": len(matched),
        "filters_applied": filters or {},
    }


def win_rate(deals: List[Dict[str, Any]], won_statuses: Optional[List[str]] = None,
             lost_statuses: Optional[List[str]] = None,
             filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Win rate = won / (won + lost). Deals still open/in-progress are
    excluded from the denominator (they haven't resolved yet).
    Status label matching is case-insensitive.
    """
    won_statuses = won_statuses or ["won", "closed won", "closed-won"]
    lost_statuses = lost_statuses or ["lost", "closed lost", "closed-lost"]

    matched = _apply_filters(deals, filters)

    won = [d for d in matched if (d.get("status") or "").strip().lower() in won_statuses]
    lost = [d for d in matched if (d.get("status") or "").strip().lower() in lost_statuses]

    resolved = len(won) + len(lost)
    rate = (len(won) / resolved * 100) if resolved > 0 else None

    return {
        "metric": "win_rate",
        "win_rate_percent": round(rate, 2) if rate is not None else None,
        "won_count": len(won),
        "lost_count": len(lost),
        "resolved_count": resolved,
        "total_deals_considered": len(matched),
        "note": "No resolved (won/lost) deals in this set." if resolved == 0 else None,
        "filters_applied": filters or {},
    }


def sector_performance(deals: List[Dict[str, Any]], filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Pipeline value and deal count grouped by sector — the classic 'how's X sector doing' query."""
    matched = _apply_filters(deals, filters)
    breakdown = defaultdict(lambda: {"deal_count": 0, "total_value": 0.0, "deals_missing_value": 0})

    for d in matched:
        sector = d.get("sector") or "Unknown"
        breakdown[sector]["deal_count"] += 1
        if d.get("deal_value") is not None:
            breakdown[sector]["total_value"] += d["deal_value"]
        else:
            breakdown[sector]["deals_missing_value"] += 1

    for sector in breakdown:
        breakdown[sector]["total_value"] = round(breakdown[sector]["total_value"], 2)

    return {
        "metric": "sector_performance",
        "breakdown": dict(breakdown),
        "total_deals": len(matched),
        "filters_applied": filters or {},
    }


# ---------------------------------------------------------------------
# WORK ORDERS / OPERATIONAL METRICS
# ---------------------------------------------------------------------

def operational_status_summary(work_orders: List[Dict[str, Any]], filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Count of work orders grouped by execution_status."""
    matched = _apply_filters(work_orders, filters)
    counts = defaultdict(int)
    for w in matched:
        status = w.get("execution_status") or "Unknown"
        counts[status] += 1

    return {
        "metric": "operational_status_summary",
        "breakdown": dict(counts),
        "total_work_orders": len(matched),
        "filters_applied": filters or {},
    }


def revenue_summary(work_orders: List[Dict[str, Any]], filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Billed vs collected vs receivable amounts across matching work orders.
    Uses amount_excl_gst as the base revenue figure (consistent, excludes tax).
    """
    matched = _apply_filters(work_orders, filters)

    def _safe_sum(key):
        valid = [w[key] for w in matched if w.get(key) is not None]
        return round(sum(valid), 2), len(valid), len(matched) - len(valid)

    total_amount, amount_count, amount_missing = _safe_sum("amount_excl_gst")
    total_billed, billed_count, billed_missing = _safe_sum("billed_value_excl_gst")
    total_collected, collected_count, collected_missing = _safe_sum("collected_amount_incl_gst")
    total_receivable, receivable_count, receivable_missing = _safe_sum("amount_receivable")

    return {
        "metric": "revenue_summary",
        "total_contracted_amount_excl_gst": total_amount,
        "total_billed_excl_gst": total_billed,
        "total_collected_incl_gst": total_collected,
        "total_receivable": total_receivable,
        "work_order_count": len(matched),
        "data_completeness": {
            "amount_missing": amount_missing,
            "billed_missing": billed_missing,
            "collected_missing": collected_missing,
            "receivable_missing": receivable_missing,
        },
        "filters_applied": filters or {},
    }


def sector_operational_performance(work_orders: List[Dict[str, Any]], filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Work order counts and revenue grouped by sector — operational counterpart to sector_performance()."""
    matched = _apply_filters(work_orders, filters)
    breakdown = defaultdict(lambda: {"work_order_count": 0, "total_amount_excl_gst": 0.0})

    for w in matched:
        sector = w.get("sector") or "Unknown"
        breakdown[sector]["work_order_count"] += 1
        if w.get("amount_excl_gst") is not None:
            breakdown[sector]["total_amount_excl_gst"] += w["amount_excl_gst"]

    for sector in breakdown:
        breakdown[sector]["total_amount_excl_gst"] = round(breakdown[sector]["total_amount_excl_gst"], 2)

    return {
        "metric": "sector_operational_performance",
        "breakdown": dict(breakdown),
        "total_work_orders": len(matched),
        "filters_applied": filters or {},
    }


# ---------------------------------------------------------------------
# CROSS-BOARD METRIC (Deals + Work Orders combined by sector)
# ---------------------------------------------------------------------

def cross_board_sector_view(deals: List[Dict[str, Any]], work_orders: List[Dict[str, Any]],
                             sector: Optional[str] = None) -> Dict[str, Any]:
    """
    Joins Deals and Work Orders data by sector, in-memory, per-request.
    This is THE demo query: 'How is Energy performing across sales and operations?'
    """
    deal_filters = {"sector": sector} if sector else None
    wo_filters = {"sector": sector} if sector else None

    deals_view = sector_performance(deals, deal_filters)
    ops_view = sector_operational_performance(work_orders, wo_filters)
    revenue_view = revenue_summary(work_orders, wo_filters)

    return {
        "metric": "cross_board_sector_view",
        "sector_filter": sector or "all",
        "sales_pipeline": deals_view,
        "operations": ops_view,
        "revenue": revenue_view,
    }


def leadership_update(deals: List[Dict[str, Any]], work_orders: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Synthesizes full company-wide business metrics across Deals and Work Orders
    for leadership and board presentations.
    """
    pipeline = total_pipeline_value(deals)
    stages = deal_count_by_stage(deals)
    rate = win_rate(deals)
    top_deal_sectors = sector_performance(deals)
    ops_status = operational_status_summary(work_orders)
    revenue = revenue_summary(work_orders)
    top_ops_sectors = sector_operational_performance(work_orders)

    return {
        "metric": "leadership_update",
        "sales_pipeline": {
            "total_value": pipeline.get("value"),
            "deal_count": pipeline.get("deal_count"),
            "deals_with_valid_value": pipeline.get("deals_with_valid_value"),
            "deals_missing_value": pipeline.get("deals_missing_value"),
            "stage_breakdown": stages.get("breakdown"),
            "win_rate_percent": rate.get("win_rate_percent"),
            "sector_breakdown": top_deal_sectors.get("breakdown"),
        },
        "operations": {
            "total_work_orders": ops_status.get("total_work_orders"),
            "status_breakdown": ops_status.get("breakdown"),
            "sector_breakdown": top_ops_sectors.get("breakdown"),
        },
        "financials": {
            "contracted_amount_excl_gst": revenue.get("total_contracted_amount_excl_gst"),
            "billed_excl_gst": revenue.get("total_billed_excl_gst"),
            "collected_incl_gst": revenue.get("total_collected_incl_gst"),
            "receivable": revenue.get("total_receivable"),
        },
    }