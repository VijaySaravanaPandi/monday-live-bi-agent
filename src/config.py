"""
Configuration loader.
Loads all sensitive/environment-specific values from .env
Never hardcode credentials or board IDs directly in source code.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    MONDAY_API_TOKEN = os.getenv("MONDAY_API_TOKEN")
    MONDAY_API_URL = os.getenv("MONDAY_API_URL", "https://api.monday.com/v2")
    DEALS_BOARD_ID = os.getenv("DEALS_BOARD_ID")
    WORK_ORDERS_BOARD_ID = os.getenv("WORK_ORDERS_BOARD_ID")

    @classmethod
    def validate(cls):
        """Fail fast and loudly if required config is missing."""
        missing = []
        if not cls.MONDAY_API_TOKEN:
            missing.append("MONDAY_API_TOKEN")
        if not cls.DEALS_BOARD_ID:
            missing.append("DEALS_BOARD_ID")
        if not cls.WORK_ORDERS_BOARD_ID:
            missing.append("WORK_ORDERS_BOARD_ID")

        if missing:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing)}. "
                f"Copy .env.example to .env and fill in real values."
            )


config = Config()