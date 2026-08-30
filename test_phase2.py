"""
Phase 2 verification script.
Fetches LIVE data from monday.com (via Phase 1's client), runs it
through the normalization layer, and prints:
1. A sample of cleaned records
2. The data quality report for each board

This proves: messy real monday.com data -> clean, consistent records
+ transparent caveats, with zero hardcoded/cached data.
"""

from src.config import config
from src.monday_client import MondayClient, MondayAPIError
from src.normalizer import normalize_deals_board, normalize_work_orders_board


def main():
    print("=== Phase 2: Data Normalization Test ===\n")

    try:
        config.validate()
    except EnvironmentError as e:
        print(f"❌ Config error: {e}")
        return

    client = MondayClient()

    # --- Deals ---
    try:
        raw_deals = client.get_deals()
        print(f"✅ Fetched {len(raw_deals)} raw deals from monday.com (live).\n")
    except MondayAPIError as e:
        print(f"❌ Could not fetch Deals: {e}")
        return

    clean_deals, deals_report = normalize_deals_board(raw_deals)

    print("--- Sample cleaned Deals (first 3) ---")
    for d in clean_deals[:3]:
        print(d)
    print()

    print("--- Deals Data Quality Report ---")
    print(deals_report.summary_text())
    print()

    # --- Work Orders ---
    try:
        raw_wos = client.get_work_orders()
        print(f"✅ Fetched {len(raw_wos)} raw work orders from monday.com (live).\n")
    except MondayAPIError as e:
        print(f"❌ Could not fetch Work Orders: {e}")
        return

    clean_wos, wo_report = normalize_work_orders_board(raw_wos)

    print("--- Sample cleaned Work Orders (first 3) ---")
    for w in clean_wos[:3]:
        print(w)
    print()

    print("--- Work Orders Data Quality Report ---")
    print(wo_report.summary_text())
    print()

    print("=== Phase 2 complete: normalization + data quality reporting verified ===")


if __name__ == "__main__":
    main()