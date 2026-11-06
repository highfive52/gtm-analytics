import hashlib
import json
from unittest.mock import Mock, patch

import pytest
from pydantic import BaseModel

from gtm_analytics.storage.dataset_writer import (
    serialize_jsonl,
    write_dataset_to_minio,
)


class SampleRecord(BaseModel):
    account_id: str
    count: int


def test_serialize_jsonl_returns_one_json_object_per_line() -> None:
    records = [
        SampleRecord(account_id="acct-001", count=2),
        SampleRecord(account_id="acct-002", count=5),
    ]

    payload = serialize_jsonl(records)
    lines = payload.decode("utf-8").splitlines()

    assert len(lines) == 2
    assert json.loads(lines[0]) == {"account_id": "acct-001", "count": 2}
    assert json.loads(lines[1]) == {"account_id": "acct-002", "count": 5}
    assert payload.endswith(b"\n")


def test_serialize_jsonl_handles_empty_dataset() -> None:
    assert serialize_jsonl([]) == b""


@patch("gtm_analytics.storage.dataset_writer.ensure_bucket_exists")
def test_writer_uploads_dataset_and_manifest(
    mock_ensure_bucket: Mock,
) -> None:
    client = Mock()
    client.list_objects.return_value = []

    records = [SampleRecord(account_id="acct-001", count=2)]

    manifest = write_dataset_to_minio(
        client,
        {"accounts": records},
        batch_id="test-batch",
    )

    mock_ensure_bucket.assert_called_once_with(client, "gtm-raw")
    assert manifest["batch_id"] == "test-batch"
    assert manifest["datasets"]["accounts"]["record_count"] == 1

    payload = serialize_jsonl(records)
    assert (
        manifest["datasets"]["accounts"]["sha256"]
        == hashlib.sha256(payload).hexdigest()
    )

    uploaded_names = [call.args[1] for call in client.put_object.call_args_list]
    assert "synthetic/batch_id=test-batch/accounts.jsonl" in uploaded_names
    assert "synthetic/batch_id=test-batch/manifest.json" in uploaded_names
    assert uploaded_names[-1] == "synthetic/batch_id=test-batch/manifest.json"


@patch("gtm_analytics.storage.dataset_writer.ensure_bucket_exists")
def test_writer_refuses_to_overwrite_existing_batch(
    mock_ensure_bucket: Mock,
) -> None:
    client = Mock()
    client.list_objects.return_value = [Mock(object_name="existing.jsonl")]

    with pytest.raises(FileExistsError):
        write_dataset_to_minio(
            client,
            {"accounts": [SampleRecord(account_id="acct-001", count=2)]},
            batch_id="baseline",
        )

    client.put_object.assert_not_called()
