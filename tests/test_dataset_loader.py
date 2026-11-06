from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from gtm_analytics.storage.dataset_loader import (
    add_ingestion_metadata,
    get_completed_batch_counts,
    load_batch_to_database,
    main,
    update_batch_audit,
)

EXPECTED_COUNTS = {
    "accounts": 24,
    "opportunities": 24,
    "activities": 2640,
    "opportunity_snapshots": 288,
}


def test_add_ingestion_metadata_adds_batch_fields_without_mutating_records():
    records = [
        {"account_id": "account_1", "name": "Acme"},
        {"account_id": "account_2", "name": "Globex"},
    ]
    original_records = [record.copy() for record in records]
    ingested_at_utc = datetime(2026, 10, 26, 16, 0, 0)

    result = add_ingestion_metadata(
        records=records,
        batch_id="test_batch",
        ingested_at_utc=ingested_at_utc,
    )

    assert len(result) == 2
    assert all(record["batch_id"] == "test_batch" for record in result)
    assert all(record["ingested_at_utc"] == ingested_at_utc for record in result)
    assert result[0]["account_id"] == "account_1"
    assert result[1]["name"] == "Globex"
    assert records == original_records
    assert result[0] is not records[0]


def test_update_batch_audit_raises_when_no_row_is_updated():
    engine = MagicMock()
    result = MagicMock()
    result.rowcount = 0

    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value = result

    with pytest.raises(
        RuntimeError,
        match="Expected to update one audit record",
    ):
        update_batch_audit(
            engine=engine,
            batch_id="missing_batch",
            status="completed",
            record_counts={"accounts": 1},
        )


def test_get_completed_batch_counts_returns_none_for_new_batch():
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.mappings.return_value.one_or_none.return_value = (
        None
    )

    result = get_completed_batch_counts(
        engine=engine,
        batch_id="new_batch",
        source_prefix="synthetic/batch_id=new_batch/",
        manifest_sha256="a" * 64,
        expected_counts=EXPECTED_COUNTS,
    )

    assert result is None


def test_get_completed_batch_counts_rejects_manifest_mismatch():
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.mappings.return_value.one_or_none.return_value = {
        "batch_id": "baseline_v2",
        "source_prefix": "synthetic/batch_id=baseline_v2/",
        "manifest_sha256": "a" * 64,
        "status": "completed",
        "record_counts": EXPECTED_COUNTS.copy(),
    }

    with pytest.raises(ValueError, match="different manifest"):
        get_completed_batch_counts(
            engine=engine,
            batch_id="baseline_v2",
            source_prefix="synthetic/batch_id=baseline_v2/",
            manifest_sha256="b" * 64,
            expected_counts=EXPECTED_COUNTS,
        )


def test_get_completed_batch_counts_rejects_non_completed_batch():
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.mappings.return_value.one_or_none.return_value = {
        "batch_id": "failed_batch",
        "source_prefix": "synthetic/batch_id=failed_batch/",
        "manifest_sha256": "a" * 64,
        "status": "failed",
        "record_counts": {},
    }

    with pytest.raises(RuntimeError, match="automatic retry is not supported"):
        get_completed_batch_counts(
            engine=engine,
            batch_id="failed_batch",
            source_prefix="synthetic/batch_id=failed_batch/",
            manifest_sha256="a" * 64,
            expected_counts=EXPECTED_COUNTS,
        )


def test_get_completed_batch_counts_returns_counts_when_batch_is_intact():
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.mappings.return_value.one_or_none.return_value = {
        "batch_id": "baseline_v2",
        "source_prefix": "synthetic/batch_id=baseline_v2/",
        "manifest_sha256": "a" * 64,
        "status": "completed",
        "record_counts": EXPECTED_COUNTS.copy(),
    }

    connection.scalar.side_effect = [24, 24, 2640, 288]

    result = get_completed_batch_counts(
        engine=engine,
        batch_id="baseline_v2",
        source_prefix="synthetic/batch_id=baseline_v2/",
        manifest_sha256="a" * 64,
        expected_counts=EXPECTED_COUNTS,
    )

    assert result == EXPECTED_COUNTS
    assert connection.scalar.call_count == 4


def test_get_completed_batch_counts_rejects_incomplete_batch():
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.mappings.return_value.one_or_none.return_value = {
        "batch_id": "baseline_v2",
        "source_prefix": "synthetic/batch_id=baseline_v2/",
        "manifest_sha256": "a" * 64,
        "status": "completed",
        "record_counts": EXPECTED_COUNTS.copy(),
    }

    connection.scalar.return_value = 23

    with pytest.raises(RuntimeError, match="expected 24"):
        get_completed_batch_counts(
            engine=engine,
            batch_id="baseline_v2",
            source_prefix="synthetic/batch_id=baseline_v2/",
            manifest_sha256="a" * 64,
            expected_counts=EXPECTED_COUNTS,
        )

    assert connection.scalar.call_count == 1


def test_load_batch_returns_existing_completed_counts_without_reloading():
    manifest = {
        "datasets": {
            name: {"record_count": count} for name, count in EXPECTED_COUNTS.items()
        }
    }
    engine = MagicMock()

    with (
        patch(
            "gtm_analytics.storage.dataset_loader.read_manifest",
            return_value=(manifest, "a" * 64),
        ),
        patch(
            "gtm_analytics.storage.dataset_loader.get_engine",
            return_value=engine,
        ),
        patch(
            "gtm_analytics.storage.dataset_loader.get_completed_batch_counts",
            return_value=EXPECTED_COUNTS,
        ) as check_batch,
        patch(
            "gtm_analytics.storage.dataset_loader.create_batch_audit",
        ) as create_audit,
        patch(
            "gtm_analytics.storage.dataset_loader.read_verified_jsonl",
        ) as read_jsonl,
    ):
        result = load_batch_to_database(
            client=MagicMock(),
            batch_id="baseline_v2",
        )

    assert result == EXPECTED_COUNTS
    check_batch.assert_called_once()
    create_audit.assert_not_called()
    read_jsonl.assert_not_called()
    engine.dispose.assert_called_once()


def test_main_loads_requested_batch_and_prints_counts(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["dataset_loader", "--batch-id", "test_batch"])
    client = MagicMock()

    with (
        patch(
            "gtm_analytics.storage.dataset_loader.get_minio_client",
            return_value=client,
        ),
        patch(
            "gtm_analytics.storage.dataset_loader.load_batch_to_database",
            return_value={"accounts": 2},
        ) as load_batch,
    ):
        main()

    load_batch.assert_called_once_with(
        client=client,
        batch_id="test_batch",
    )
    assert capsys.readouterr().out == '{\n  "accounts": 2\n}\n'
