import hashlib
import json
from collections.abc import Sequence
from io import BytesIO

from minio import Minio
from pydantic import BaseModel

from gtm_analytics.storage.minio_client import ensure_bucket_exists

GENERATOR_VERSION = "1.0.0"
OBJECT_PREFIX = "synthetic"


def serialize_jsonl(records: Sequence[BaseModel]) -> bytes:
    """Serialize Pydantic records as UTF-8 JSON Lines."""
    lines = [record.model_dump_json() for record in records]
    if not lines:
        return b""
    return ("\n".join(lines) + "\n").encode("utf-8")


def upload_bytes(
    client: Minio,
    bucket_name: str,
    object_name: str,
    payload: bytes,
    content_type: str,
) -> None:
    """Upload a byte payload to MinIO."""
    client.put_object(
        bucket_name,
        object_name,
        data=BytesIO(payload),
        length=len(payload),
        content_type=content_type,
    )


def write_dataset_to_minio(
    client: Minio,
    datasets: dict[str, Sequence[BaseModel]],
    batch_id: str = "baseline",
    bucket_name: str = "gtm-raw",
) -> dict:
    """Write JSONL datasets and a manifest to an immutable batch prefix."""
    if not batch_id or "/" in batch_id or batch_id in {".", ".."}:
        raise ValueError("batch_id must be a non-empty path-safe value")

    ensure_bucket_exists(client, bucket_name)

    prefix = f"{OBJECT_PREFIX}/batch_id={batch_id}/"

    # Fail before uploading anything if this batch prefix is already occupied.
    existing_objects = list(
        client.list_objects(bucket_name, prefix=prefix, recursive=True)
    )
    if existing_objects:
        raise FileExistsError(
            f"Batch already contains objects: s3://{bucket_name}/{prefix}"
        )

    manifest = {
        "batch_id": batch_id,
        "generator_version": GENERATOR_VERSION,
        "datasets": {},
    }

    payloads: dict[str, bytes] = {}

    for dataset_name, records in datasets.items():
        if not dataset_name or "/" in dataset_name:
            raise ValueError(f"Invalid dataset name: {dataset_name!r}")

        payload = serialize_jsonl(records)
        object_name = f"{prefix}{dataset_name}.jsonl"

        payloads[object_name] = payload
        manifest["datasets"][dataset_name] = {
            "object_name": object_name,
            "record_count": len(records),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size_bytes": len(payload),
        }

    # Upload data objects first.
    for object_name, payload in payloads.items():
        upload_bytes(
            client,
            bucket_name,
            object_name,
            payload,
            "application/x-ndjson",
        )

    # Upload the manifest last so it describes the completed upload.
    manifest_payload = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )

    upload_bytes(
        client,
        bucket_name,
        f"{prefix}manifest.json",
        manifest_payload,
        "application/json",
    )

    return manifest
