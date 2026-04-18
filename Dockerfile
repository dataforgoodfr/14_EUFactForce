# Use a slim Debian Trixie image as our base
# (we don't use a Python image because Python will be installed with uv)
FROM ghcr.io/astral-sh/uv:trixie-slim

# Set the working directory inside the container
WORKDIR /app

# Arguments needed at build-time, to be provided by Coolify
ARG DEBUG
ARG SECRET_KEY

# Install system dependencies needed by our app
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Put the venv outside /app so the .:/app bind mount never shadows it
ENV UV_PROJECT_ENVIRONMENT=/venv
# Put the HF model cache outside /app for the same reason
ENV HF_HOME=/hf_cache

# Copy only the dependency definitions first to leverage Docker's layer caching
COPY pyproject.toml uv.lock ./

# Install runtime dependencies only. Dev group (pytest, jupyter, ruff, etc.) is
# installed locally, not in the production image — keeps the image and build
# time reasonable on low-spec deploy hosts.
RUN uv sync

# Copy the rest of the application code into the container
COPY . .

# Copy and set up entrypoint (migrations + collectstatic at container startup)
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose the port Gunicorn will run on
EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
# PYTHONPATH: /app for eu_fact_force.*, /app/eu_fact_force for app.settings (used in wsgi)
ENV PYTHONPATH=/app:/app/eu_fact_force
CMD ["uv", "run", "--no-sync", "gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--preload", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info", "eu_fact_force.app.wsgi:application"]
