.PHONY: config init up ps start verify down logs test lint lint-fix check fix publish-baseline load-dataset analytics-db analytics-db-check analytics-db-migrate analytics-db-update analytics-db-apply analytics-db-require-message

# Validate the Compose configuration
config:
	docker compose config

# Initialize Airflow's metadata database and admin user
init:
	docker compose up airflow-init

# Start the services
up:
	docker compose up -d

# List service status
ps:
	docker compose ps

# Initialize and start the full environment
start: config init up

# Start the environment and inspect container status
verify: start ps

# Stop services without deleting persistent volumes
down:
	docker compose down

# Stop services and delete persistent volumes
down-volumes:
	docker compose down -v

# Follow service logs
logs:
	docker compose logs -f

# Run the Python test suite
test:
	uv run pytest

# Start the analytics PostgreSQL database
analytics-db:
	docker compose up -d analytics-postgres

# Wait until analytics PostgreSQL is healthy
analytics-db-check:
	@until [ "$$(docker compose ps --format json analytics-postgres | grep -c '"Health":"healthy"')" -gt 0 ]; do \
		echo "Waiting for analytics PostgreSQL to become healthy..."; \
		sleep 2; \
	done
	@echo "Analytics PostgreSQL is healthy."

# Apply pending analytics database migrations
analytics-db-migrate: analytics-db analytics-db-check
	docker compose exec -T analytics-postgres \
		sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -c "CREATE SCHEMA IF NOT EXISTS public;"'
	uv run alembic upgrade head

# Check code quality with Ruff
lint:
	uv run ruff check .

# Automatically fix supported Ruff issues
lint-fix:
	uv run ruff check . --fix
	uv run ruff format .

# Run tests and lint checks
check: test lint

# Run tests and lint checks
fix: test lint-fix lint

# Publish a synthetic dataset batch to MinIO
# example usage:
#   make publish-baseline BATCH_ID=baseline_v2

BATCH_ID ?= baseline_v2

publish-baseline:
	set -a; if [ -f .env ]; then . ./.env; fi; set +a; \
	MINIO_ENDPOINT=localhost:9000 \
	MINIO_ACCESS_KEY="$${MINIO_ROOT_USER:-minioadmin}" \
	MINIO_SECRET_KEY="$${MINIO_ROOT_PASSWORD:-minioadmin123}" \
	MINIO_SECURE=false \
	uv run python -m gtm_analytics.synthetic.publish_baseline \
		--batch-id $(BATCH_ID)

# Load a published synthetic dataset batch into analytics PostgreSQL
# example usage:
#   make load-dataset BATCH_ID=baseline_v2
load-dataset:
	set -a; if [ -f .env ]; then . ./.env; fi; set +a; \
	MINIO_ENDPOINT=localhost:9000 \
	MINIO_ACCESS_KEY="$${MINIO_ROOT_USER:-minioadmin}" \
	MINIO_SECRET_KEY="$${MINIO_ROOT_PASSWORD:-minioadmin123}" \
	MINIO_SECURE=false \
	uv run python -m gtm_analytics.storage.dataset_loader \
		--batch-id $(BATCH_ID)