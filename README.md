make config   # Validate compose.yaml
make init     # Initialize Airflow
make up       # Start services
make ps       # Check container status
make start    # Run all four steps in sequence
make verify   # Alias for start
make down     # Stop containers, preserve data
make logs     # Follow logs

docker compose config
docker compose up airflow-init
docker compose up -d
docker compose ps