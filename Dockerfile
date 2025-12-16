# Dockerfile for FLAMEHAVEN FileSearch API
# Phase 2: Semantic Search with DSP v2.0 Algorithm
# Zero ML dependencies - Pure algorithmic implementation

FROM python:3.11-slim

# Metadata
LABEL maintainer="Flamehaven Team"
LABEL version="1.3.1"
LABEL description="Flamehaven FileSearch with Semantic Search (DSP v2.0)"
LABEL phase="Phase 2 - Semantic Resonance"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY flamehaven_filesearch/ ./flamehaven_filesearch/
COPY pyproject.toml README.md ./

# Install package
RUN pip install -e ".[api]"

# Create temp directory for uploads
RUN mkdir -p /tmp/uploads

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Run API server
CMD ["flamehaven-api"]
