FROM python:3.12-slim AS builder

ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    # pip:
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    # poetry:
    POETRY_VERSION=1.7.1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR='/var/cache/pypoetry'

# Install Poetry
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION" && poetry --version

# Set work directory
WORKDIR /code

# Copy pyproject.toml and poetry.lock
COPY pyproject.toml poetry.lock /code/

# Install dependencies
RUN poetry install --no-root --no-dev

# Final stage
FROM python:3.12-slim

LABEL org.opencontainers.image.title="DEX Aggregator Benchmark"
LABEL org.opencontainers.image.description="Benchmark for DEX aggregators on TON blockchain"
LABEL org.opencontainers.image.source="https://github.com/ilyaqznetsow/dex-aggregator"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.created="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

# Set work directory
WORKDIR /code

# Create a non-root user for better security
RUN adduser --disabled-password --gecos "" appuser

# Create results directory with proper permissions
RUN mkdir -p /code/results && chown -R appuser:appuser /code

USER appuser

# Copy dependencies from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the application code
COPY . .

ENV PYTHONPATH=/code

CMD ["python", "run.py"]