import argparse
import json

from gtm_analytics.storage.dataset_writer import write_dataset_to_minio
from gtm_analytics.storage.minio_client import get_minio_client
from gtm_analytics.storage.validate_dataset import validate_uploaded_batch
from gtm_analytics.synthetic.generator import (
    generate_accounts,
    generate_activities,
    generate_opportunities,
    generate_opportunity_snapshots,
)


def publish_baseline(batch_id: str = "baseline") -> dict:
    """Generate, publish, and validate a synthetic dataset batch."""
    accounts = generate_accounts()
    opportunities = generate_opportunities(accounts)
    snapshots = generate_opportunity_snapshots(opportunities)
    activities = generate_activities(accounts)

    datasets = {
        "accounts": accounts,
        "opportunities": opportunities,
        "opportunity_snapshots": snapshots,
        "activities": activities,
    }

    client = get_minio_client()

    manifest = write_dataset_to_minio(
        client=client,
        datasets=datasets,
        batch_id=batch_id,
        bucket_name="gtm-raw",
    )

    validation_result = validate_uploaded_batch(
        client=client,
        batch_id=batch_id,
        bucket_name="gtm-raw",
    )

    print("Dataset validation:")
    print(json.dumps(validation_result, indent=2, sort_keys=True))

    return manifest


def main() -> None:
    """Parse arguments and publish the requested dataset batch."""
    parser = argparse.ArgumentParser(
        description="Generate, publish, and validate a synthetic GTM dataset."
    )
    parser.add_argument(
        "--batch-id",
        default="baseline",
        help="Batch ID to publish (default: baseline). Existing batches are not overwritten.",
    )
    args = parser.parse_args()

    manifest = publish_baseline(batch_id=args.batch_id)

    print("Published manifest:")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
