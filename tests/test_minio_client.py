from unittest.mock import Mock, patch

from minio import Minio

from gtm_analytics.storage.minio_client import (
    ensure_bucket_exists,
    get_minio_client,
)


@patch.dict(
    "os.environ",
    {
        "MINIO_ENDPOINT": "localhost:9000",
        "MINIO_ROOT_USER": "test-access",
        "MINIO_ROOT_PASSWORD": "test-secret",
        "MINIO_SECURE": "false",
    },
)
@patch("gtm_analytics.storage.minio_client.Minio")
def test_get_minio_client_from_environment(mock_minio):
    client = get_minio_client()

    mock_minio.assert_called_once_with(
        "localhost:9000",
        access_key="test-access",
        secret_key="test-secret",
        secure=False,
    )
    assert client == mock_minio.return_value


def test_ensure_bucket_exists_does_not_recreate_existing_bucket():
    client = Mock(spec=Minio)
    client.bucket_exists.return_value = True

    ensure_bucket_exists(client)

    client.bucket_exists.assert_called_once_with("gtm-raw")
    client.make_bucket.assert_not_called()


def test_ensure_bucket_exists_creates_missing_bucket():
    client = Mock(spec=Minio)
    client.bucket_exists.return_value = False

    ensure_bucket_exists(client)

    client.bucket_exists.assert_called_once_with("gtm-raw")
    client.make_bucket.assert_called_once_with("gtm-raw")
