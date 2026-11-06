from datetime import UTC, datetime

from sqlalchemy import select

from gtm_analytics.db.config import get_engine
from gtm_analytics.db.models import BatchAudit
from gtm_analytics.storage.dataset_loader import (
    create_batch_audit,
    update_batch_audit,
)


def main() -> None:
    batch_id = f"audit_test_{datetime.now(UTC):%Y%m%dT%H%M%S}"

    engine = get_engine()

    try:
        create_batch_audit(
            engine=engine,
            batch_id=batch_id,
            source_prefix="synthetic/audit-test/",
            manifest_sha256="0" * 64,
        )

        update_batch_audit(
            engine=engine,
            batch_id=batch_id,
            status="failed",
            record_counts={},
            error_message="Simulated validation failure",
        )

        with engine.connect() as connection:
            audit = (
                connection.execute(
                    select(BatchAudit.__table__).where(BatchAudit.batch_id == batch_id)
                )
                .mappings()
                .one()
            )

        print(f"batch_id: {audit['batch_id']}")
        print(f"status: {audit['status']}")
        print(f"record_counts: {audit['record_counts']}")
        print(f"started_at_utc: {audit['started_at_utc']}")
        print(f"completed_at_utc: {audit['completed_at_utc']}")

        assert audit["status"] == "failed"
        assert audit["error_message"] == "Simulated validation failure"
        assert audit["completed_at_utc"] is not None

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
