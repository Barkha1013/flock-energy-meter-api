"""Application settings kept small and environment-driven."""

import os

from dotenv import load_dotenv

load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/meters.db")
PORTAL_BASE_URL = os.getenv("PORTAL_BASE_URL", "https://urja-ops.flockenergy.tech").rstrip("/")
PORTAL_USERNAME = os.getenv("PORTAL_USERNAME", "")
PORTAL_PASSWORD = os.getenv("PORTAL_PASSWORD", "")
PORTAL_TIMEOUT_SECONDS = float(os.getenv("PORTAL_TIMEOUT_SECONDS", "15"))


def portal_credentials_configured() -> bool:
    return bool(PORTAL_USERNAME and PORTAL_PASSWORD)
