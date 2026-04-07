"""ALB OIDC JWT authentication middleware.

Validates the X-Amzn-OIDC-Data header injected by the ALB after PingID OIDC
authentication. In AUTH_LOCAL_MODE the header is skipped and a synthetic
anonymous UserContext is injected instead.

Note: exact header forwarding must be confirmed once ALB ARN is known.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from question_answer import config

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 10

# Public key cache with TTL — ALB rotates signing keys periodically.
# Each entry: { cache_key: (public_key_pem, fetched_at_epoch) }
_KEY_CACHE_TTL_SECONDS = 3600
_pub_key_cache: dict[str, tuple[str, float]] = {}


@dataclass
class UserContext:
    """Claims extracted from the ALB-injected OIDC JWT."""

    sso_id: str
    email: str
    first_name: str
    last_name: str


def _error(status_code: int, message: str) -> JSONResponse:
    response = JSONResponse(status_code=status_code, content={"message": message})
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


async def _fetch_public_key(kid: str) -> str:
    """Fetch ALB public key for the given key ID, with TTL-based caching.

    Uses httpx async client to avoid blocking the event loop.
    Cache entries expire after _KEY_CACHE_TTL_SECONDS to handle ALB key rotation.
    """
    cache_key = f"{config.ALB_REGION}:{kid}"
    cached = _pub_key_cache.get(cache_key)
    if cached is not None:
        pem, fetched_at = cached
        if time.monotonic() - fetched_at < _KEY_CACHE_TTL_SECONDS:
            return pem

    url = f"https://public-keys.auth.elb.{config.ALB_REGION}.amazonaws.com/{kid}"
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    _pub_key_cache[cache_key] = (resp.text, time.monotonic())
    return resp.text


async def _validate_alb_jwt(encoded_jwt: str) -> dict[str, Any]:
    """Decode and verify the ALB-injected OIDC JWT."""
    header_b64 = encoded_jwt.split(".")[0]
    # ALB uses base64url without padding — add padding if needed
    padding = 4 - len(header_b64) % 4
    header_b64 += "=" * (padding % 4)
    decoded_header = json.loads(base64.b64decode(header_b64).decode())

    received_arn = decoded_header["signer"]
    if config.EXPECTED_ALB_ARN and config.EXPECTED_ALB_ARN != received_arn:
        raise ValueError(f"Invalid ALB signer: {received_arn}")

    kid = decoded_header["kid"]
    public_key = await _fetch_public_key(kid)

    return jwt.decode(encoded_jwt, public_key, algorithms=["ES256"])


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate ALB OIDC JWT and inject UserContext + session_id into request.state."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Health and readiness endpoints always pass — no auth needed for probes
        if request.url.path in {"/health", "/ready", "/ping"}:
            return await call_next(request)  # type: ignore[no-any-return]

        if config.AUTH_LOCAL_MODE:
            logger.debug("AUTH_LOCAL_MODE — injecting anonymous UserContext")
            request.state.user_context = UserContext(
                sso_id="local-dev",
                email="dev@localhost",
                first_name="Local",
                last_name="Dev",
            )
            request.state.session_id = request.headers.get(config.SESSION_ID_HEADER)
            return await call_next(request)  # type: ignore[no-any-return]

        encoded_jwt = request.headers.get("X-Amzn-OIDC-Data")
        if not encoded_jwt:
            return _error(401, "Missing X-Amzn-OIDC-Data header")

        try:
            claims = await _validate_alb_jwt(encoded_jwt)
        except Exception as exc:
            logger.warning("JWT validation failed: %s", exc)
            return _error(401, "Invalid authentication token")

        request.state.user_context = UserContext(
            sso_id=claims.get("sub", ""),
            email=claims.get("email", ""),
            first_name=claims.get("given_name", ""),
            last_name=claims.get("family_name", ""),
        )
        request.state.session_id = request.headers.get(config.SESSION_ID_HEADER)

        if config.REQUIRE_SESSION_ID and not request.state.session_id:
            return _error(400, f"Missing {config.SESSION_ID_HEADER} header")

        return await call_next(request)  # type: ignore[no-any-return]
