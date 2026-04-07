# ==============================================================================
# sdg-data-service -- Pure FastAPI REST + NakshaClient
# Build context: backend/ (uv workspace root)
# Port: 8001
# ==============================================================================
FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy workspace root (pyproject + lock) and this agent
COPY pyproject.toml uv.toml .python-version uv.lock ./
COPY libs/ ./libs/
COPY services/data-service/ ./services/data-service/
COPY certs/ ./certs/

# Install only this agent's deps (no dev group, frozen lock)
RUN uv sync --frozen --no-dev --package sdg-data-service

# Build a merged CA bundle: certifi's trusted roots + any extra certs in
# backend/certs/ (e.g. GE/corporate root CAs).  Avoids needing apt-get.
COPY certs/ /app/certs/
RUN /app/.venv/bin/python -c 'import certifi,shutil; shutil.copy(certifi.where(), "/app/ca-bundle.crt")' \
    && cat /app/certs/*.crt >> /app/ca-bundle.crt 2>/dev/null; \
    cat /app/certs/*.pem >> /app/ca-bundle.crt 2>/dev/null; \
    echo "CA bundle ready: $(wc -c < /app/ca-bundle.crt) bytes"

# Tell Python, requests, and urllib3 (Databricks connector) to use this bundle
ENV SSL_CERT_FILE=/app/ca-bundle.crt
ENV REQUESTS_CA_BUNDLE=/app/ca-bundle.crt

# Non-root user
RUN useradd --create-home --home-dir /home/appuser --shell /bin/false appuser \
     && mkdir -p /home/appuser/.cache/uv \
     && chown -R appuser:appuser /home/appuser
ENV HOME=/home/appuser
ENV UV_CACHE_DIR=/home/appuser/.cache/uv
ENV PATH="/app/.venv/bin:${PATH}"
USER appuser

EXPOSE 8086

CMD ["uvicorn", "data_service.main:app", \
     "--host", "0.0.0.0", "--port", "8086", "--workers", "1"]
