"""Logging stub for SDG usecase services.

.. note:: TEMPORARY — minimal stdlib passthrough that preserves the
   ``get_logger(name)`` call signature so all service code can be written
   against the stable API today.  When the platform logging library ships,
   replace the body of ``get_logger`` with the platform import — no callers
   need to change.

Usage (stable API — do NOT change)::

    from commons.logging import get_logger

    log = get_logger(__name__)
    log.info("agent started")
"""

from __future__ import annotations

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)

# Suppress noisy Databricks SQL connector logs (keepalive/polling every ~10s)
logging.getLogger("databricks.sql.auth.retry").setLevel(logging.WARNING)
logging.getLogger("databricks.sql.auth.thrift_http_client").setLevel(logging.WARNING)


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a stdlib logger that writes to *stdout*.

    This is a passthrough shim.  It will be replaced by the platform
    logging library when it becomes available.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    return logger
