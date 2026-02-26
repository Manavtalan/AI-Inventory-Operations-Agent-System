# =============================================================================
# Stage 1: Builder — installs dependencies in a virtual environment
# =============================================================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual environment for isolation
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# =============================================================================
# Stage 2: Final — lean runtime image without build tools
# =============================================================================
FROM python:3.11-slim AS final

WORKDIR /app

# Install only runtime system dependencies (libpq for asyncpg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy the compiled virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create a non-root user for security
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --no-create-home appuser

# Copy application source code
COPY --chown=appuser:appgroup . .

# Switch to non-root user
USER appuser

# Expose application port
EXPOSE 8000

# Default: run FastAPI application
# Override CMD in docker-compose for worker/beat services
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
