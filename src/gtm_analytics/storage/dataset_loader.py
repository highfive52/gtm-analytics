import argparse
import hashlib
import json
from datetime import UTC, datetime

from minio import Minio
from sqlalchemy import func, insert, select, update

from gtm_analytics.contracts.account import Account as AccountContract
from gtm_analytics.contracts.activity import Activity as ActivityContract
from gtm_analytics.contracts.opportunity import Opportunity as OpportunityContract
from gtm_analytics.contracts.opportunity_snapshot import (
    OpportunitySnapshot as OpportunitySnapshotContract,
)
from gtm_analytics.db.config import get_engine
from gtm_analytics.db.models import (
    Account as AccountModel,
)
from gtm_analytics.db.models import (
    Activity as ActivityModel,
)
from gtm_analytics.db.models import (
    BatchAudit,
)
from gtm_analytics.db.models import (
    Opportunity as OpportunityModel,
)
from gtm_analytics.db.models import (
    OpportunitySnapshot as OpportunitySnapshotModel,
)
from gtm_analytics.storage.minio_client import get_minio_client


def read_manifest(
    client: Minio,
    bucket_name: str = "gtm-raw",
    batch_id: str = "baseline_v2",
) -> tuple[dict, str]:
    """Read a manifest and return its contents and SHA-256 checksum."""
    object_name = f"synthetic/batch_id={batch_id}/manifest.json"
    response = client.get_object(bucket_name, object_name)

    try:
        payload = response.read()
    finally:
        response.close()
        response.release_conn()

    manifest = json.loads(payload.decode("utf-8"))
    manifest_sha256 = hashlib.sha256(payload).hexdigest()

    return manifest, manifest_sha256


def read_verified_jsonl(
    client: Minio,
    object_name: str,
    expected_sha256: str,
    expected_record_count: int,
    bucket_name: str = "gtm-raw",
) -> list[dict]:
    """Read JSONL records and verify their checksum and count."""
    response = client.get_object(bucket_name, object_name)

    try:
        payload = response.read()
    finally:
        response.close()
        response.release_conn()

    actual_sha256 = hashlib.sha256(payload).hexdigest()

    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"SHA-256 mismatch for {object_name}: "
            f"expected {expected_sha256}, got {actual_sha256}"
        )

    records = [
        json.loads(line)
        for line in payload.decode("utf-8").splitlines()
        if line.strip()
    ]

    if len(records) != expected_record_count:
        raise ValueError(
            f"Record count mismatch for {object_name}: "
            f"expected {expected_record_count}, got {len(records)}"
        )

    return records


CONTRACTS = {
    "accounts": AccountContract,
    "activities": ActivityContract,
    "opportunities": OpportunityContract,
    "opportunity_snapshots": OpportunitySnapshotContract,
}

UTC_TIMESTAMP_FIELDS = {
    "accounts": ("created_at_utc", "updated_at_utc"),
    "activities": ("activity_timestamp_utc",),
    "opportunities": ("created_at_utc", "updated_at_utc"),
    "opportunity_snapshots": (),
}


def validate_records(
    dataset_name: str,
    records: list[dict],
) -> list[dict]:
    """Restore stored UTC timestamps and validate records against contracts."""
    try:
        contract = CONTRACTS[dataset_name]
        timestamp_fields = UTC_TIMESTAMP_FIELDS[dataset_name]
    except KeyError as exc:
        raise ValueError(f"Unknown dataset: {dataset_name}") from exc

    validated_records = []

    for record in records:
        normalized_record = record.copy()

        for field in timestamp_fields:
            value = normalized_record[field]
            parsed = datetime.fromisoformat(value)

            if parsed.tzinfo is not None:
                raise ValueError(f"{dataset_name}.{field} must be stored as naive UTC")

            normalized_record[field] = parsed.replace(tzinfo=UTC)

        validated = contract.model_validate(normalized_record)
        validated_records.append(validated.model_dump(mode="python"))

    return validated_records


DATABASE_MODELS = {
    "accounts": AccountModel,
    "activities": ActivityModel,
    "opportunities": OpportunityModel,
    "opportunity_snapshots": OpportunitySnapshotModel,
}

LOAD_ORDER = (
    "accounts",
    "opportunities",
    "activities",
    "opportunity_snapshots",
)


def create_batch_audit(
    engine,
    batch_id: str,
    source_prefix: str,
    manifest_sha256: str,
) -> None:
    """Create and commit the initial audit record for a batch."""
    with engine.begin() as connection:
        connection.execute(
            insert(BatchAudit.__table__).values(
                batch_id=batch_id,
                source_prefix=source_prefix,
                manifest_sha256=manifest_sha256,
                status="loading",
                started_at_utc=datetime.now(UTC).replace(tzinfo=None),
                completed_at_utc=None,
                record_counts={},
                error_message=None,
            )
        )


def update_batch_audit(
    engine,
    batch_id: str,
    status: str,
    record_counts: dict[str, int] | None = None,
    error_message: str | None = None,
    connection=None,
) -> None:
    """Update the final status and outcome of a batch."""

    def execute_update(connection) -> None:
        result = connection.execute(
            update(BatchAudit.__table__)
            .where(BatchAudit.batch_id == batch_id)
            .values(
                status=status,
                completed_at_utc=datetime.now(UTC).replace(tzinfo=None),
                record_counts=record_counts or {},
                error_message=error_message,
            )
        )

        if result.rowcount != 1:
            raise RuntimeError(
                f"Expected to update one audit record for batch "
                f"{batch_id!r}, updated {result.rowcount}"
            )

    if connection is not None:
        execute_update(connection)
    else:
        with engine.begin() as transaction:
            execute_update(transaction)


def add_ingestion_metadata(
    records: list[dict],
    batch_id: str,
    ingested_at_utc: datetime,
) -> list[dict]:
    """Add persistence metadata without mutating validated source records."""
    return [
        {
            **record,
            "batch_id": batch_id,
            "ingested_at_utc": ingested_at_utc,
        }
        for record in records
    ]


def get_completed_batch_counts(
    engine,
    batch_id: str,
    source_prefix: str,
    manifest_sha256: str,
    expected_counts: dict[str, int],
) -> dict[str, int] | None:
    """Return counts for an already-loaded batch, or None if it is new."""
    with engine.connect() as connection:
        audit = (
            connection.execute(
                select(BatchAudit.__table__).where(BatchAudit.batch_id == batch_id)
            )
            .mappings()
            .one_or_none()
        )

        if audit is None:
            return None

        if audit["manifest_sha256"] != manifest_sha256:
            raise ValueError(
                f"Batch {batch_id!r} already exists with a different manifest"
            )

        if audit["source_prefix"] != source_prefix:
            raise ValueError(
                f"Batch {batch_id!r} already exists with a different source prefix"
            )

        if audit["status"] != "completed":
            raise RuntimeError(
                f"Batch {batch_id!r} already exists with status "
                f"{audit['status']!r}; automatic retry is not supported yet"
            )

        recorded_counts = audit["record_counts"]

        for dataset_name in LOAD_ORDER:
            model = DATABASE_MODELS[dataset_name]
            actual_count = connection.scalar(
                select(func.count())
                .select_from(model.__table__)
                .where(model.batch_id == batch_id)
            )
            expected_count = expected_counts[dataset_name]

            if actual_count != expected_count:
                raise RuntimeError(
                    f"Batch {batch_id!r} has {actual_count} rows in "
                    f"{model.__tablename__}; expected {expected_count}"
                )

            if recorded_counts.get(dataset_name) != expected_count:
                raise RuntimeError(
                    f"Audit count mismatch for batch {batch_id!r}, "
                    f"dataset {dataset_name!r}"
                )

        return recorded_counts


def load_batch_to_database(
    client: Minio,
    batch_id: str = "baseline_v2",
    bucket_name: str = "gtm-raw",
) -> dict[str, int]:
    """Validate and load a batch, recording its outcome in the audit table."""
    manifest, manifest_sha256 = read_manifest(client, bucket_name, batch_id)
    engine = get_engine()
    source_prefix = f"synthetic/batch_id={batch_id}/"

    expected_counts = {
        dataset_name: manifest["datasets"][dataset_name]["record_count"]
        for dataset_name in LOAD_ORDER
    }

    try:
        completed_counts = get_completed_batch_counts(
            engine=engine,
            batch_id=batch_id,
            source_prefix=source_prefix,
            manifest_sha256=manifest_sha256,
            expected_counts=expected_counts,
        )

        if completed_counts is not None:
            return completed_counts

        create_batch_audit(
            engine=engine,
            batch_id=batch_id,
            source_prefix=source_prefix,
            manifest_sha256=manifest_sha256,
        )

        try:
            validated_datasets = {}

            # Verify and validate the complete batch.
            for dataset_name in LOAD_ORDER:
                metadata = manifest["datasets"][dataset_name]
                records = read_verified_jsonl(
                    client,
                    object_name=metadata["object_name"],
                    expected_sha256=metadata["sha256"],
                    expected_record_count=metadata["record_count"],
                    bucket_name=bucket_name,
                )
                validated_datasets[dataset_name] = validate_records(
                    dataset_name,
                    records,
                )

            loaded_counts = {}

            # Data inserts commit or roll back as a single transaction.
            with engine.begin() as connection:
                for dataset_name in LOAD_ORDER:
                    model = DATABASE_MODELS[dataset_name]
                    count = connection.scalar(
                        select(func.count()).select_from(model.__table__)
                    )
                    if count:
                        raise RuntimeError(
                            f"Table {model.__tablename__} already contains "
                            f"{count} rows; refusing to load batch {batch_id!r}"
                        )

                # Use one ingestion timestamp for the entire batch.
                ingested_at_utc = datetime.now(UTC).replace(tzinfo=None)

                for dataset_name in LOAD_ORDER:
                    model = DATABASE_MODELS[dataset_name]
                    records = validated_datasets[dataset_name]

                    # Add persistence metadata without changing source contracts.
                    persisted_records = add_ingestion_metadata(
                        records=records,
                        batch_id=batch_id,
                        ingested_at_utc=ingested_at_utc,
                    )

                    if persisted_records:
                        connection.execute(
                            insert(model.__table__),
                            persisted_records,
                        )

                    loaded_counts[dataset_name] = len(persisted_records)

                update_batch_audit(
                    engine=engine,
                    batch_id=batch_id,
                    status="completed",
                    record_counts=loaded_counts,
                    connection=connection,
                )

            return loaded_counts

        except Exception as exc:
            update_batch_audit(
                engine=engine,
                batch_id=batch_id,
                status="failed",
                error_message=str(exc)[:4000],
            )
            raise

    finally:
        engine.dispose()


def main() -> None:
    """Load a published batch into the analytics database."""
    parser = argparse.ArgumentParser(
        description="Load a validated synthetic GTM batch into PostgreSQL."
    )
    parser.add_argument(
        "--batch-id",
        default="baseline_v2",
        help="Batch ID to load (default: baseline_v2).",
    )
    args = parser.parse_args()

    record_counts = load_batch_to_database(
        client=get_minio_client(),
        batch_id=args.batch_id,
    )
    print(json.dumps(record_counts, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
