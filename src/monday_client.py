"""
Monday.com API Client
----------------------
Read-only adapter responsible for ALL communication with monday.com.

Design principles (per assignment constraints):
- READ ONLY: no mutation queries anywhere in this file.
- DYNAMIC: every call hits the live monday.com API. Nothing is cached
  or persisted here. No CSV data is ever loaded from disk.
- Graceful error handling: network/API failures raise a clear,
  typed exception instead of crashing silently or returning bad data.
"""

import requests
import time
import logging
from typing import Optional
from src.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("monday_client")


class MondayAPIError(Exception):
    """Raised when the monday.com API returns an error or is unreachable."""
    pass


class MondayClient:
    def __init__(self, api_token: Optional[str] = None, api_url: Optional[str] = None):
        self.api_token = api_token or config.MONDAY_API_TOKEN
        self.api_url = api_url or config.MONDAY_API_URL

        if not self.api_token:
            raise MondayAPIError(
                "No monday.com API token found. Set MONDAY_API_TOKEN in your .env file."
            )

        self.headers = {
            "Authorization": self.api_token,
            "Content-Type": "application/json",
        }

    def _execute(self, query: str, variables: Optional[dict] = None, retries: int = 3) -> dict:
        """
        Executes a GraphQL query against monday.com with retry + backoff.
        This is the single choke point all read operations go through,
        so error handling lives in exactly one place.
        """
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        last_error = None

        for attempt in range(1, retries + 1):
            try:
                response = requests.post(
                    self.api_url,
                    json=payload,
                    headers=self.headers,
                    timeout=15,
                )

                if response.status_code == 401:
                    raise MondayAPIError(
                        "Authentication failed. Check that MONDAY_API_TOKEN is valid."
                    )

                if response.status_code >= 500:
                    raise MondayAPIError(
                        f"monday.com server error (status {response.status_code})."
                    )

                data = response.json()

                if "errors" in data:
                    raise MondayAPIError(f"monday.com API returned errors: {data['errors']}")

                return data.get("data", {})

            except (requests.ConnectionError, requests.Timeout) as e:
                last_error = e
                wait = 2 ** attempt  # exponential backoff: 2s, 4s, 8s
                logger.warning(
                    f"Attempt {attempt}/{retries} failed ({e}). Retrying in {wait}s..."
                )
                time.sleep(wait)
            except MondayAPIError:
                raise  # don't retry on auth/logic errors, only network errors

        raise MondayAPIError(
            f"Failed to reach monday.com after {retries} attempts. Last error: {last_error}"
        )

    def test_connection(self) -> dict:
        """Simple sanity check: fetch the current account's user info."""
        query = """
        query {
            me {
                id
                name
                email
            }
        }
        """
        return self._execute(query)

    def get_board_columns(self, board_id: str) -> list:
        """
        Fetches ONLY the column structure (names, types, ids) of a board.
        This is metadata, not data — safe to reference/reason about
        without violating the 'no hardcoded data' constraint.
        """
        query = """
        query ($boardId: [ID!]) {
            boards (ids: $boardId) {
                id
                name
                columns {
                    id
                    title
                    type
                }
            }
        }
        """
        result = self._execute(query, variables={"boardId": [board_id]})
        boards = result.get("boards", [])
        if not boards:
            raise MondayAPIError(f"Board {board_id} not found or inaccessible.")
        return boards[0]["columns"]

    def get_board_items(self, board_id: str, limit: int = 100) -> list:
        """
        Fetches ALL items (rows) and their column values from a board, live.
        This is the core dynamic read operation — called fresh on every query,
        never cached to disk or database.
        """
        query = """
        query ($boardId: [ID!], $limit: Int) {
            boards (ids: $boardId) {
                id
                name
                items_page (limit: $limit) {
                    cursor
                    items {
                        id
                        name
                        column_values {
                            id
                            text
                            value
                            column {
                                title
                                type
                            }
                        }
                    }
                }
            }
        }
        """
        result = self._execute(query, variables={"boardId": [board_id], "limit": limit})
        boards = result.get("boards", [])
        if not boards:
            raise MondayAPIError(f"Board {board_id} not found or inaccessible.")

        items_page = boards[0].get("items_page", {})
        items = items_page.get("items", [])

        # Handle pagination if the board has more items than one page
        cursor = items_page.get("cursor")
        while cursor:
            more = self._get_next_page(cursor)
            items.extend(more.get("items", []))
            cursor = more.get("cursor")

        return items

    def _get_next_page(self, cursor: str) -> dict:
        """Follows pagination cursor for boards with many items."""
        query = """
        query ($cursor: String!) {
            next_items_page (cursor: $cursor) {
                cursor
                items {
                    id
                    name
                    column_values {
                        id
                        text
                        value
                        column {
                            title
                            type
                        }
                    }
                }
            }
        }
        """
        result = self._execute(query, variables={"cursor": cursor})
        return result.get("next_items_page", {})

    def get_deals(self) -> list:
        """Convenience method: fetch live Deals board data."""
        return self.get_board_items(config.DEALS_BOARD_ID)

    def get_work_orders(self) -> list:
        """Convenience method: fetch live Work Orders board data."""
        return self.get_board_items(config.WORK_ORDERS_BOARD_ID)