import os
from pathlib import Path

from dotenv import load_dotenv
from minio import Minio

PROJECT_ROOT = Path(__file__).resolve().parents[3]

load_dotenv(PROJECT_ROOT / ".env")


def get_minio_client() -> Minio:
    """Create a MinIO client using environment-based configuration."""
    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    access_key = os.environ["MINIO_ROOT_USER"]
    secret_key = os.environ["MINIO_ROOT_PASSWORD"]
    secure = os.getenv("MINIO_SECURE", "false").lower() == "true"

    return Minio(
        endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure,
    )


def ensure_bucket_exists(
    client: Minio,
    bucket_name: str = "gtm-raw",
) -> None:
    """Create the bucket if it does not already exist."""
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)
