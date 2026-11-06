import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine

# Project root: .../gtm-analytics/
PROJECT_ROOT = Path(__file__).resolve().parents[3]

load_dotenv(PROJECT_ROOT / ".env")


def get_database_url() -> URL:
    """Build the analytics PostgreSQL URL from environment settings."""
    return URL.create(
        drivername="postgresql+psycopg",
        username=os.environ["ANALYTICS_POSTGRES_USER"],
        password=os.environ["ANALYTICS_POSTGRES_PASSWORD"],
        host=os.getenv("ANALYTICS_POSTGRES_HOST", "localhost"),
        port=int(os.getenv("ANALYTICS_POSTGRES_PORT", "5433")),
        database=os.environ["ANALYTICS_POSTGRES_DB"],
    )


def get_engine():
    """Create a SQLAlchemy engine for the analytics database."""
    return create_engine(get_database_url(), pool_pre_ping=True)
