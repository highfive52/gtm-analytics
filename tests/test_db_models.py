from gtm_analytics.db import models  # noqa: F401
from gtm_analytics.db.base import Base


def test_all_database_models_use_raw_schema() -> None:
    tables = Base.metadata.sorted_tables

    assert {table.name for table in tables} == {
        "accounts",
        "activities",
        "opportunities",
        "opportunity_snapshots",
        "batch_audit",
    }
    assert all(table.schema == "raw" for table in tables)
