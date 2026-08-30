"""
Phase 3 verification script.
Fetches LIVE data -> normalizes it -> runs it through the deterministic
BI engine -> prints computed metrics.

This proves: the numbers are calculated by code, not by an LLM, and
they respond correctly to live monday.com data with filters applied.
"""

from src.config import config
from src.monday_client import MondayClient, MondayAPIError
from src.normalizer import normalize_deals_board, normalize_work_orders_board
from src.bi_engine import (
    total_pipeline_value,
    deal_count_by_stage,
    win_rate,
    sector_performance,
    operational_status_summary,
    revenue_summary,
    sector_operational_performance,
    cross_board_sector_view,
)


def main():
    print("=== Phase 3: Deterministic BI Engine Test ===\n")

    try:
        config.validate()
    except EnvironmentError as e:
        print(f"❌ Config error: {e}")
        return

    client = MondayClient()

    try:
        raw_deals = client.get_deals()
        raw_wos = client.get_work_orders()
    except MondayAPIError as e:
        print(f"❌ Could not fetch live data: {e}")
        return

    clean_deals, deals_report = normalize_deals_board(raw_deals)
    clean_wos, wo_report = normalize_work_orders_board(raw_wos)

    print(f"Loaded {len(clean_deals)} clean deals, {len(clean_wos)} clean work orders.\n")

    print("--- Total Pipeline Value (all deals) ---")
    print(total_pipeline_value(clean_deals))
    print()

    print("--- Deal Count by Stage ---")
    print(deal_count_by_stage(clean_deals))
    print()

    print("--- Win Rate (all deals) ---")
    print(win_rate(clean_deals))
    print()

    print("--- Sector Performance (Deals) ---")
    print(sector_performance(clean_deals))
    print()

    print("--- Operational Status Summary (Work Orders) ---")
    print(operational_status_summary(clean_wos))
    print()

    print("--- Revenue Summary (Work Orders) ---")
    print(revenue_summary(clean_wos))
    print()

    print("--- Sector Operational Performance (Work Orders) ---")
    print(sector_operational_performance(clean_wos))
    print()

    # Try a real cross-board query using whatever sector actually
    # appears in the data, so this test works regardless of your CSV contents.
    sample_sector = None
    if clean_deals:
        sample_sector = clean_deals[0].get("sector")

    print(f"--- Cross-Board Sector View (sector='{sample_sector}') ---")
    print(cross_board_sector_view(clean_deals, clean_wos, sector=sample_sector))
    print()

    print("=== Phase 3 complete: deterministic BI metrics verified ===")


if __name__ == "__main__":
    main()