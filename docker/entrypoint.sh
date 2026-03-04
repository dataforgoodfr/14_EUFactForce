#!/bin/bash
set -e

# Run database migrations at container startup
uv run --no-sync ./manage.py migrate --noinput

# Collect static files (needs DATABASE_URL from env)
uv run --no-sync ./manage.py collectstatic --noinput

# Execute the main command (gunicorn)
exec "$@"
