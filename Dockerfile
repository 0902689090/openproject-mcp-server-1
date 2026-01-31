# Multi-stage build for smaller image size
FROM python:3.11-slim as builder

WORKDIR /app

# Install uv for faster dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml requirements.txt ./

# Install dependencies
RUN uv pip install --system --no-cache -r requirements.txt

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ ./src/
COPY pyproject.toml ./

# Set PYTHONPATH to include src directory
ENV PYTHONPATH=/app/src:$PYTHONPATH

# Create non-root user for security
RUN useradd -m -u 1000 mcpuser && \
    chown -R mcpuser:mcpuser /app

USER mcpuser

# Environment variables (can be overridden at runtime)
ENV OPENPROJECT_URL="" \
    OPENPROJECT_API_KEY="" \
    USE_HTTP_TRANSPORT="true" \
    HTTP_HOST="0.0.0.0" \
    HTTP_PORT="8008"

# Expose FastMCP default port
EXPOSE 8008

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8008/mcp').read()" || exit 1

# Run the server
CMD ["python", "-m", "openproject_mcp_server"]
