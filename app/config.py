"""Application settings kept small and environment-driven."""

import os

from dotenv import load_dotenv

load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/meters.db")
