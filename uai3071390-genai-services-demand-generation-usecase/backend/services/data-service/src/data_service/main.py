"""Data Service -- pure FastAPI REST + MCP Server.

A single NakshaClient instance is created once at startup and stored in
app.state.naksha_client.  Routes read it via request.app.state.

Port: 8001

Routes registered:
  GET  /health
  GET  /api/v1/ibat/health
  GET  /api/v1/ibat/equipment?equip_serial_number={esn}
  POST /api/v1/prism/read
  GET  /api/v1/prism/health
  GET  /api/v1/heatmap/load?equipment_type={}&persona={}&component={}
  GET  /api/v1/er/cases?serial_number={esn}&component={}
  POST /api/v1/er/risk-er-cases
  GET  /api/v1/retriever/health
  POST /api/v1/retriever/retrieve
  GET  /api/v1/heatmap/load?equipment_type={GEN|GT}&persona={REL|OE}&component={}
  GET  /api/v1/heatmap/health


MCP server mounted at /mcp (streamable-http transport)
"""

from __future__ import annotations

import os

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from commons.logging import get_logger
from data_service import config
from data_service.client import NakshaClient
from data_service.routes import assessments, documents, equipment, er, heatmap, ibat, internal, prism, retriever, units

logger = get_logger("data_service.main")

# ========== MCP Server Integration ==========
# Initialize MCP server and session manager for lifespan
mcp_server = None
mcp_session_manager = None

try:
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    import data_service.mcp.server as mcp_server_module
    from data_service.mcp.server import create_mcp_server

    # Override DATA_SERVICE_URL to point to localhost (same server)
    # This ensures MCP tools call the REST endpoints on the same server
    mcp_server_module.DATA_SERVICE_URL = os.getenv("DATA_SERVICE_URL", "http://localhost:8086")
    logger.info(f"[MCP] Using DATA_SERVICE_URL: {mcp_server_module.DATA_SERVICE_URL}")

    # Create placeholder FastAPI app to generate OpenAPI spec
    temp_app = FastAPI(title="SDG Data Service", version="0.1.0")

    # Add all routers to temp app
    temp_app.include_router(ibat.router)
    temp_app.include_router(prism.router)
    temp_app.include_router(heatmap.router)
    temp_app.include_router(er.router)
    temp_app.include_router(units.router)
    temp_app.include_router(equipment.router)
    temp_app.include_router(documents.router)
    temp_app.include_router(retriever.router)
    temp_app.include_router(assessments.router)

    @temp_app.get("/health")
    def temp_health() -> dict[str, str]:
        return {"status": "ok"}

    # Generate OpenAPI spec
    openapi_spec = temp_app.openapi()

    # Create MCP server with the OpenAPI spec
    mcp_server = create_mcp_server(openapi_spec)

    # Create session manager for the MCP server
    mcp_session_manager = StreamableHTTPSessionManager(
        app=mcp_server._mcp_server,  # Access the underlying MCP server
        event_store=None,
        retry_interval=None,
        json_response=False,
        stateless=False,
    )

    logger.info("[MCP] Initialized MCP server and session manager")
except Exception as e:
    logger.error(f"[MCP] Warning: Failed to initialize MCP server: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Combined lifespan context for FastAPI and MCP server."""
    mode = "mock" if config.USE_MOCK else "live"
    logger.info("data-service: starting (mode=%s)", mode)
    try:
        app.state.naksha_client = NakshaClient()

        # Start MCP server and session manager lifespan if available
        if mcp_server and mcp_session_manager:
            async with mcp_server._lifespan_manager(), mcp_session_manager.run():
                logger.info("[MCP] MCP server and session manager started")
                yield
        else:
            yield
    except Exception as exc:
        logger.error("data-service: startup error: %s", exc, exc_info=True)
        raise
    finally:
        logger.info("data-service: shutdown")


app = FastAPI(
    title="SDG Data Service",
    description="Pure FastAPI REST data service with MCP server. NakshaClient SQL proxy.",
    version="0.1.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

# CORS — allow all origins in local/dev mode; tighten via CORS_ORIGINS env var in prod.
_cors_origins = [
    o.strip()
    for o in config.__dict__.get("CORS_ORIGINS", "*").split(",")
    if o.strip()
] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler for uncaught errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Uncaught exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "An internal error occurred"},
    )


app.include_router(ibat.router)
app.include_router(prism.router)
app.include_router(heatmap.router)
app.include_router(er.router)
# app.include_router(er.router, prefix="/dataservices")
app.include_router(units.router)
app.include_router(equipment.router)
app.include_router(documents.router)
app.include_router(retriever.router)
# Canonical assessments API path (ALB-aligned).
# app.include_router(assessments.router, prefix="/dataservices/api/v1")
# Legacy compatibility path used by existing clients/tests.
app.include_router(assessments.router)
# app.include_router(assessments.router, prefix="/api")
app.include_router(internal.router)


# Mount the MCP server if it was successfully initialized
if mcp_session_manager:
    try:
        from fastmcp.server.http import StreamableHTTPASGIApp
        from starlette.applications import Starlette
        from starlette.routing import Route

        # Create the ASGI app wrapper
        mcp_asgi_app = StreamableHTTPASGIApp(mcp_session_manager)

        # Create a simple Starlette app with the MCP endpoint
        # Note: No lifespan here since we handle it in the main FastAPI app
        mcp_starlette_app = Starlette(
            routes=[
                Route("/", endpoint=mcp_asgi_app, methods=["GET", "POST", "DELETE"]),
            ],
            debug=False,
        )

        # Mount the Starlette app at /mcp
        app.mount("/dataservices/mcp", mcp_starlette_app)
        logger.info("[MCP] Mounted MCP server at /dataservices/mcp/ (streamable-http transport)")
    except Exception as e:
        logger.error(f"[MCP] Failed to mount MCP server: {e}", exc_info=True)

@app.get("/health")
@app.get("/dataservices/")
@app.get("/dataservices/health")
async def health() -> dict[str, str]:
    mode = "mock" if config.USE_MOCK else "live"
    return {"status": "ok", "service": "data-service", "mode": mode}
