from sqlalchemy import func, select

from gtm_analytics.db.config import get_engine
from gtm_analytics.db.models import (
    Account,
    Activity,
    BatchAudit,
    Opportunity,
    OpportunitySnapshot,
)
from gtm_analytics.storage.dataset_loader import (
    LOAD_ORDER,
    create_batch_audit,
    read_manifest,
    update_batch_audit,
)
from gtm_analytics.storage.minio_client import get_minio_client


def main() -> None:
    batch_id = "baseline_v2"
    bucket_name = "gtm-raw"
    source_prefix = f"synthetic/batch_id={batch_id}/"

    models = {
        "accounts": Account,
        "opportunities": Opportunity,
        "activities": Activity,
        "opportunity_snapshots": OpportunitySnapshot,
    }

    client = get_minio_client()
    manifest, manifest_sha256 = read_manifest(
        client,
        bucket_name=bucket_name,
        batch_id=batch_id,
    )
    expected_counts = {
        name: manifest["datasets"][name]["record_count"] for name in LOAD_ORDER
    }

    engine = get_engine()
    try:
        with engine.connect() as connection:
            existing_audit = connection.execute(
                select(BatchAudit.batch_id).where(BatchAudit.batch_id == batch_id)
            ).first()

            if existing_audit is not None:
                raise RuntimeError(
                    f"Audit record for {batch_id!r} already exists; "
                    "refusing to reconcile automatically"
                )

            actual_counts = {}
            for name in LOAD_ORDER:
                model = models[name]
                count = connection.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.batch_id == batch_id)
                )
                actual_counts[name] = count

        if actual_counts != expected_counts:
            raise RuntimeError(
                f"Database counts do not match manifest: "
                f"database={actual_counts}, manifest={expected_counts}"
            )

        create_batch_audit(
            engine=engine,
            batch_id=batch_id,
            source_prefix=source_prefix,
            manifest_sha256=manifest_sha256,
        )
        update_batch_audit(
            engine=engine,
            batch_id=batch_id,
            status="completed",
            record_counts=actual_counts,
        )

        print("Reconciled audit record:")
        print(f"  batch_id: {batch_id}")
        print("  status: completed")
        print(f"  manifest_sha256: {manifest_sha256}")
        print(f"  record_counts: {actual_counts}")

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
