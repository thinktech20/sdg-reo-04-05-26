# ==============================================================================
# sdg-qna-agent — Strands SDK + FastAPI
# Build context: backend/ (uv workspace root)
# Port: 8087
# ==============================================================================
FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy workspace root (pyproject + lock) and this agent
COPY pyproject.toml uv.toml .python-version uv.lock ./
COPY libs/ ./libs/
COPY agents/question-answer-agent/ ./agents/question-answer-agent/
COPY certs/ /app/certs/

# Install only this agent's deps (no dev group, frozen lock)
RUN uv sync --frozen --no-dev --package sdg-qna-agent \
     # Security pin: litellm 1.82.7 and 1.82.8 were compromised (PYSEC-2026-2 / MAL-2026-2144).
     && VIRTUAL_ENV=/app/.venv uv pip install --no-cache "litellm==1.82.4" "uvicorn[standard]" \
     && /app/.venv/bin/python -c 'import uvicorn; print("uvicorn installed")' \
     && /app/.venv/bin/python -c 'import certifi,shutil; shutil.copy(certifi.where(), "/app/ca-bundle.crt")' \
     && (cat /app/certs/*.crt >> /app/ca-bundle.crt 2>/dev/null || true) \
     && (cat /app/certs/*.pem >> /app/ca-bundle.crt 2>/dev/null || true) \
     && echo "CA bundle ready: $(wc -c < /app/ca-bundle.crt) bytes"

# Tell Python, requests, and botocore to use the merged CA bundle.
ENV SSL_CERT_FILE=/app/ca-bundle.crt
ENV REQUESTS_CA_BUNDLE=/app/ca-bundle.crt
ENV AWS_CA_BUNDLE=/app/ca-bundle.crt

# Non-root user
RUN useradd --create-home --home-dir /home/appuser --shell /bin/false appuser \
     && mkdir -p /home/appuser/.cache/uv \
     && chown -R appuser:appuser /home/appuser
ENV HOME=/home/appuser
ENV UV_CACHE_DIR=/home/appuser/.cache/uv
ENV PATH="/app/.venv/bin:${PATH}"
USER appuser

EXPOSE 8087

CMD ["uvicorn", "question_answer.main:app", \
     "--host", "0.0.0.0", "--port", "8087", "--workers", "1"]
