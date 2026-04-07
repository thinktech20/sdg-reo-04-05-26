# Shared auth middleware — stub, pending ALB OIDC header confirmation.
#
# This package will contain the ASGI middleware that:
#   1. Reads the ``X-Amzn-OIDC-Data`` JWT from the ALB.
#   2. Decodes it (no signature verification needed — ALB already validated it).
#   3. Populates ``request.state.user`` with a ``UserContext`` instance.
#
# All agents and services should depend on this package rather than
# reimplementing auth header parsing.
