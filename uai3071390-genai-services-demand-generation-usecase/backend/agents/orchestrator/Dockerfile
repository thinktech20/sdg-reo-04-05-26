# ==============================================================================
# sdg-orchestrator -- LangGraph + FastAPI pipeline dispatcher
# Build context: backend/ (uv workspace root)
# Port: 8006
# ==============================================================================
FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy workspace root (pyproject + lock) and this agent
COPY pyproject.toml uv.toml .python-version uv.lock ./
COPY libs/ ./libs/
COPY agents/orchestrator/ ./agents/orchestrator/

# Install only this agent's deps (no dev group, frozen lock)
RUN uv sync --frozen --no-dev --package sdg-orchestrator \
     # Security pin: litellm 1.82.7 and 1.82.8 were compromised (PYSEC-2026-2 / MAL-2026-2144).
     && VIRTUAL_ENV=/app/.venv uv pip install --no-cache "litellm==1.82.4"

# Non-root user
RUN useradd --create-home --home-dir /home/appuser --shell /bin/false appuser \
     && mkdir -p /home/appuser/.cache/uv \
     && chown -R appuser:appuser /home/appuser
ENV HOME=/home/appuser
ENV UV_CACHE_DIR=/home/appuser/.cache/uv
ENV PATH="/app/.venv/bin:${PATH}"
USER appuser

EXPOSE 8081

CMD ["uvicorn", "orchestrator.main:app", \
     "--host", "0.0.0.0", "--port", "8081", "--workers", "1"]
