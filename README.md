# GTM Analytics

GTM Analytics is a small data platform for exploring a practical go-to-market question: **which accounts are showing increased product usage while their sales opportunities are stalled, and which should the GTM team follow up with?**

The project demonstrates an end-to-end data engineering workflow, from deterministic synthetic data generation through validation, object storage, and relational database loading.

The platform currently provides:

- **Validated data contracts** for accounts, opportunities, opportunity snapshots, and product or GTM activities.
- **Deterministic synthetic data generation** designed to exercise varied GTM scenarios.
- **Manifest-driven datasets** with record counts and checksums for validating published data.
- **MinIO object storage** for published JSON Lines datasets and manifests.
- **PostgreSQL ingestion** with batch identifiers and ingestion timestamps for data lineage.
- **Batch audit and reconciliation** to track load status, record counts, and consistency between audit metadata and stored records.
- **dbt snapshots** that preserve observed versions of the raw tables in a `src` schema.
- **A Streamlit dashboard** for visualizing weekly account usage and follow-up priority.
- **A local development environment** using Docker Compose, Airflow, PostgreSQL, and MinIO.

The loader verifies published batches before inserting their records into PostgreSQL. It also checks completed batches before loading, allowing a verified completed batch to be rerun without inserting its records again.

The generated data and scenario assumptions are described in [docs/business_scenarios.md](docs/business_scenarios.md) and [docs/dataset_shape.md](docs/dataset_shape.md). Field definitions are documented in the [data dictionary](docs/data_dict.md).

## Quick start

Prerequisites:

- Docker with the Compose plugin.
- Python 3.12 or newer and [`uv`](https://docs.astral.sh/uv/getting-started/installation/).
- [GNU Make](https://www.gnu.org/software/make/).

On Windows, native PowerShell and Command Prompt are not verified; the Makefile
uses POSIX shell syntax. Use [WSL 2](https://learn.microsoft.com/windows/wsl/install)
and run the commands below from its Linux terminal. Install `uv` and GNU Make
inside your WSL distribution. For Docker, install
[Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)
and enable its [WSL 2 integration](https://docs.docker.com/desktop/features/wsl/)
for that distribution.

From the repository root, run:

```sh
cp .env.example .env
uv sync --dev --extra dashboard
make start
make publish-baseline
make analytics-db-migrate
make load-dataset
make dbt-build
make streamlit
```

The `.env.example` values are local demo defaults; do not use them in production.
These commands start the local services, generate, upload, and validate the
`baseline_v2` synthetic batch in MinIO, apply Alembic migrations to create the
analytics PostgreSQL schema, and load the batch records into PostgreSQL.
`make dbt-build` runs dbt snapshots against the loaded raw tables, builds the
warehouse and mart models, and runs their data tests. `make streamlit` starts
the read-only dashboard at <http://localhost:8501>; it visualizes the two
tables in the PostgreSQL `mart` schema and refreshes cached data every 60
seconds. Run `make dbt-build` before opening the dashboard to create or update
those tables.

Published MinIO batch prefixes are immutable and are not overwritten. If
`baseline_v2` has already been published, load that existing batch with
`make load-dataset BATCH_ID=baseline_v2`, or publish and load a new batch using
the same new ID for both commands:

```sh
make publish-baseline BATCH_ID=baseline_v3
make load-dataset BATCH_ID=baseline_v3
```

Loading a successfully completed batch again with the same ID is idempotent:
the loader verifies the manifest, audit record, and stored row counts, then
returns the counts without inserting duplicate rows. A different batch ID is
treated as a new batch, not as permission to append: the current loader only
loads into empty target tables and rejects a new batch if any target table
already contains rows.

### Clean up the environment

Stop and remove the containers while keeping the stored MinIO and PostgreSQL
data:

```sh
make down
```

To also delete the persistent data volumes and fully reset the sandbox, run:

```sh
make down-volumes
```

`make down-volumes` permanently deletes the data stored in the Compose volumes.

## Architecture

The current workflow separates dataset generation, raw storage, relational ingestion, and dbt snapshots:

1. **Generate:** Create deterministic synthetic GTM datasets using defined business scenarios.
2. **Validate and publish:** Validate the datasets, generate a manifest, and publish the JSON Lines files and manifest to MinIO.
3. **Load:** Verify the published manifest and dataset contents, validate records against the data contracts, and load the data into PostgreSQL.
4. **Snapshot:** Use dbt to preserve source versions observed at each snapshot run in the `src` schema.
5. **Model:** Build dimensions and facts in the `wh` schema, then reporting marts in the `mart` schema.
6. **Audit and reconcile:** Record batch status and counts, and verify that the completed batch agrees with the stored records.
7. **Visualize:** Use the read-only Streamlit dashboard to explore the two reporting marts.

MinIO preserves the published batch as the source for ingestion, while PostgreSQL provides relational tables for downstream analytics. Batch identifiers and ingestion timestamps support lineage and reconciliation.

## Start the local environment

You need Docker with the Compose plugin and `make`. From the repository root, run:

```sh
make start
```

This validates the Compose configuration, initializes Airflow's metadata database, and starts the services in the background. The first run may take a few minutes while Docker downloads the service images.

Check service status with:

```sh
make ps
```

Once the services are running:

- Airflow UI: [http://localhost:8080](http://localhost:8080)
- MinIO console: [http://localhost:9001](http://localhost:9001)
- MinIO API: [http://localhost:9000](http://localhost:9000)
- Analytics PostgreSQL: `localhost:5433`

Airflow authentication and service credentials are configured through environment variables; Compose provides local development defaults.

Stop the services WITHOUT REMOVING their stored data with:

```sh
make down
```

Stop the services AND REMOVE their stored data with:

```sh
make down-volumnes
```

## Generate and publish a synthetic data batch

Start the local environment with `make start` and install the Python dependencies with `uv sync --dev`.

Generate, upload, and validate a batch in MinIO:

```sh
make publish-baseline
```

By default, the command publishes batch `baseline_v2` to the `gtm-raw` bucket. Choose a new batch ID for each run because existing batches are not overwritten:

```sh
make publish-baseline BATCH_ID=baseline_v3
```

The command prints the validation result and published manifest. The uploaded JSON Lines datasets and manifest are stored under:

```text
synthetic/batch_id=<batch-id>/
```

The manifest provides dataset metadata used to verify the published files and expected record counts during ingestion.

## Load and audit a batch

The ingestion workflow reads the published batch from MinIO, verifies its manifest and dataset contents, validates the records, and loads them into PostgreSQL.

Run the loader after publishing the batch and applying the database migrations:

```sh
make load-dataset
```

By default, this loads `baseline_v2`. To load a different published batch, pass
the same batch ID used when publishing:

```sh
make load-dataset BATCH_ID=baseline_v3
```

Each loaded record carries its source `batch_id` and `ingested_at_utc` timestamp. A separate batch audit record tracks the source prefix, manifest checksum, processing status, and per-dataset record counts.

For a completed batch, the loader verifies that the manifest, audit metadata, and database row counts agree. If they do, a rerun returns the existing counts without inserting the batch again. If the source manifest or stored data does not match the completed audit record, the loader raises an error rather than silently reloading the batch.

The current loader is designed for the initial load into empty target tables, with safe reruns of a previously completed batch. It is not yet a general-purpose incremental loader for adding arbitrary new batches to populated tables.

## Snapshot raw tables with dbt

The dbt project is isolated under `dbt/`, keeping its project configuration,
models, snapshots, and macros separate from the Python application and
Alembic migrations.

After the raw tables have been migrated and loaded, create or update their dbt
snapshots with:

```sh
make dbt-snapshot
```

The dbt project reads `raw.accounts`, `raw.activities`, `raw.opportunities`,
and `raw.opportunity_snapshots`, and creates the corresponding snapshot tables
in the PostgreSQL `src` schema. Accounts and opportunities use their
`updated_at_utc` columns with dbt's timestamp strategy. Activities and
opportunity snapshots use the check strategy, comparing all selected source
columns. Snapshot tables include dbt's validity metadata, including
`dbt_valid_from` and `dbt_valid_to`.

These are standard dbt snapshots: they record the source state observed when
dbt runs. Run the snapshot command after loading or changing raw data. If a
source row changes multiple times between dbt runs, dbt records the state it
sees on the next run, not every intermediate state.

## Build the `wh` and `mart` schemas

After loading the raw batch, build the snapshots, `wh` tables, and data
tests with:

```sh
make dbt-build
```

The dbt project builds both schemas:

| Schema | Table | Grain / purpose |
|---|---|---|
| `wh` | `dim_date` | One row per calendar date used by the source data |
| `wh` | `dim_account` | SCD2 account versions with effective date boundaries |
| `wh` | `dim_opportunity` | Current opportunity attributes; stage history remains in the fact |
| `wh` | `fact_activity` | One row per activity event |
| `wh` | `fact_opportunity_snapshot` | One row per opportunity and weekly snapshot date |
| `mart` | `account_weekly_usage` | Account activity counts by week, including zero-activity weeks |
| `mart` | `account_follow_up_priority` | Account-opportunity usage trends, stage age, flags, and reasons |

The `mart` models are separate from the `wh` dimensions and facts, but remain
in the same dbt project so their `ref()` dependencies are managed together.
The primary follow-up mart compares average activity in the latest four
complete weeks with the preceding four complete weeks. It flags an account and
opportunity when usage increased and the opportunity is open and has remained
in its current stage for at least 30 days. Stage age comes from the weekly
opportunity history, not `updated_at_utc`; because the history is weekly, stage
age is approximate to that snapshot interval. The activity windows are anchored
to the latest complete week in the loaded data, making the result reproducible
for historical batches. The mart includes the component metrics and a reason
so dashboard users can inspect why a record was flagged.

## Python development

Python 3.12 or newer and [uv](https://docs.astral.sh/uv/) are required for the Python package and development commands.

### Database schema changes

After changing the SQLAlchemy models, generate a migration with a descriptive
message:

```sh
make analytics-db-update MIGRATION_MESSAGE="add account segment"
```

This starts and checks the analytics database, applies existing migrations,
then generates a candidate migration in `alembic/versions/`. Review the
generated migration before applying it:

```sh
make analytics-db-apply
```

### Tests and linting

Install the project and development dependencies, then run the tests and linter:

```sh
uv sync --dev
uv run pytest
uv run ruff check .
```
