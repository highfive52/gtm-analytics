import hashlib
import json
from collections import Counter
from datetime import date
from itertools import pairwise

from minio import Minio
from pydantic import BaseModel

from gtm_analytics.contracts.account import Account
from gtm_analytics.contracts.activity import Activity
from gtm_analytics.contracts.opportunity import Opportunity
from gtm_analytics.contracts.opportunity_snapshot import OpportunitySnapshot

RECORD_MODELS: dict[str, type[BaseModel]] = {
    "accounts": Account,
    "opportunities": Opportunity,
    "opportunity_snapshots": OpportunitySnapshot,
    "activities": Activity,
}


def download_object(client: Minio, bucket: str, object_name: str) -> bytes:
    """Download an object and always release the MinIO response."""
    response = client.get_object(bucket, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def parse_jsonl(
    payload: bytes, model: type[BaseModel], dataset_name: str
) -> list[BaseModel]:
    """Parse JSONL and validate canonical stored UTC timestamps."""
    records: list[BaseModel] = []

    utc_fields_by_dataset = {
        "accounts": ("created_at_utc", "updated_at_utc"),
        "opportunities": ("created_at_utc", "updated_at_utc"),
        "activities": ("activity_timestamp_utc",),
    }
    utc_fields = utc_fields_by_dataset.get(dataset_name, ())

    for line_number, line in enumerate(payload.splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"{dataset_name}.jsonl has a blank line at {line_number}")

        try:
            record_data = json.loads(line)

            for field in utc_fields:
                value = record_data.get(field)
                if isinstance(value, str) and not value.endswith(("Z", "+00:00")):
                    record_data[field] = f"{value}+00:00"

            records.append(model.model_validate(record_data))
        except Exception as exc:
            raise ValueError(
                f"Invalid {dataset_name} record at line {line_number}: {exc}"
            ) from exc

    return records


def validate_uploaded_batch(
    client: Minio,
    batch_id: str = "baseline",
    bucket_name: str = "gtm-raw",
) -> dict:
    """Validate uploaded object integrity, contracts, and relationships."""
    prefix = f"synthetic/batch_id={batch_id}/"
    manifest_bytes = download_object(client, bucket_name, f"{prefix}manifest.json")
    manifest = json.loads(manifest_bytes)

    if manifest.get("batch_id") != batch_id:
        raise ValueError("Manifest batch_id does not match requested batch")

    parsed: dict[str, list[BaseModel]] = {}

    for dataset_name, model in RECORD_MODELS.items():
        try:
            metadata = manifest["datasets"][dataset_name]
        except KeyError as exc:
            raise ValueError(f"Manifest is missing dataset: {dataset_name}") from exc

        object_name = metadata["object_name"]
        if not object_name.startswith(prefix):
            raise ValueError(f"{dataset_name} object is outside the batch prefix")

        payload = download_object(client, bucket_name, object_name)

        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if actual_sha256 != metadata["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {object_name}")

        if len(payload) != metadata["size_bytes"]:
            raise ValueError(f"Byte-size mismatch for {object_name}")

        records = parse_jsonl(payload, model, dataset_name)

        if len(records) != metadata["record_count"]:
            raise ValueError(f"Record-count mismatch for {object_name}")

        parsed[dataset_name] = records

    accounts = parsed["accounts"]
    opportunities = parsed["opportunities"]
    snapshots = parsed["opportunity_snapshots"]
    activities = parsed["activities"]

    account_ids = [record.account_id for record in accounts]
    if len(account_ids) != len(set(account_ids)):
        raise ValueError("Duplicate account_id values")

    opportunity_ids = [record.opportunity_id for record in opportunities]
    if len(opportunity_ids) != len(set(opportunity_ids)):
        raise ValueError("Duplicate opportunity_id values")

    activity_ids = [record.activity_id for record in activities]
    if len(activity_ids) != len(set(activity_ids)):
        raise ValueError("Duplicate activity_id values")

    known_accounts = set(account_ids)
    for record in [*opportunities, *activities, *snapshots]:
        if record.account_id not in known_accounts:
            raise ValueError(f"Unknown account_id {record.account_id!r}")

    known_opportunities = set(opportunity_ids)
    for record in snapshots:
        if record.opportunity_id not in known_opportunities:
            raise ValueError(f"Unknown opportunity_id {record.opportunity_id!r}")

    snapshot_keys = [
        (record.opportunity_id, record.snapshot_date) for record in snapshots
    ]
    if len(snapshot_keys) != len(set(snapshot_keys)):
        raise ValueError("Duplicate opportunity/date snapshots")

    snapshots_per_opportunity = Counter(record.opportunity_id for record in snapshots)
    if set(snapshots_per_opportunity) != known_opportunities:
        raise ValueError("Snapshot opportunities do not match opportunities")

    bad_snapshot_counts = {
        opportunity_id: count
        for opportunity_id, count in snapshots_per_opportunity.items()
        if count != 12
    }
    if bad_snapshot_counts:
        raise ValueError(
            f"Expected 12 snapshots per opportunity: {bad_snapshot_counts}"
        )

    # Verify that each opportunity's snapshots are on weekly dates.
    dates_by_opportunity: dict[str, list[date]] = {}
    for record in snapshots:
        dates_by_opportunity.setdefault(record.opportunity_id, []).append(
            record.snapshot_date
        )

    for opportunity_id, dates in dates_by_opportunity.items():
        ordered_dates = sorted(dates)
        for earlier, later in pairwise(ordered_dates):
            if (later - earlier).days != 7:
                raise ValueError(
                    f"Snapshots for {opportunity_id} are not exactly 7 days apart"
                )
    return {
        "batch_id": batch_id,
        "status": "passed",
        "record_counts": {name: len(records) for name, records in parsed.items()},
    }
