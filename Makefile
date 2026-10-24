
.PHONY: config init up ps start verify down logs test lint check

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

# Follow service logs
logs:
	docker compose logs -f

# Run the Python test suite
test:
	uv run pytest

# Check code quality with Ruff
lint:
	uv run ruff check .

# Run tests and lint checks
check: test lint
