"""
Phase 1 verification script.
Run this after setting up your .env to confirm:
1. Config loads correctly
2. Monday.com authentication works
3. Both boards are reachable and returning live data
"""

from src.config import config
from src.monday_client import MondayClient, MondayAPIError


def main():
    print("=== Phase 1: Monday.com Connection Test ===\n")

    try:
        config.validate()
        print("✅ Config loaded successfully.\n")
    except EnvironmentError as e:
        print(f"❌ Config error: {e}")
        return

    client = MondayClient()

    try:
        me = client.test_connection()
        print(f"✅ Authenticated as: {me['me']['name']} ({me['me']['email']})\n")
    except MondayAPIError as e:
        print(f"❌ Authentication failed: {e}")
        return

    try:
        deals_columns = client.get_board_columns(config.DEALS_BOARD_ID)
        print(f"✅ Deals board columns ({len(deals_columns)} found):")
        for col in deals_columns:
            print(f"   - {col['title']} ({col['type']})")
        print()
    except MondayAPIError as e:
        print(f"❌ Could not read Deals board: {e}")
        return

    try:
        wo_columns = client.get_board_columns(config.WORK_ORDERS_BOARD_ID)
        print(f"✅ Work Orders board columns ({len(wo_columns)} found):")
        for col in wo_columns:
            print(f"   - {col['title']} ({col['type']})")
        print()
    except MondayAPIError as e:
        print(f"❌ Could not read Work Orders board: {e}")
        return

    try:
        deals = client.get_deals()
        print(f"✅ Fetched {len(deals)} live items from Deals board.")
    except MondayAPIError as e:
        print(f"❌ Could not fetch Deals items: {e}")
        return

    try:
        work_orders = client.get_work_orders()
        print(f"✅ Fetched {len(work_orders)} live items from Work Orders board.")
    except MondayAPIError as e:
        print(f"❌ Could not fetch Work Orders items: {e}")
        return

    print("\n=== Phase 1 complete: live, read-only, dynamic connection verified ===")


if __name__ == "__main__":
    main()