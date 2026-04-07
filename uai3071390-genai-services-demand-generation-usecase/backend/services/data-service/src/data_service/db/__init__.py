"""DynamoDB table abstractions for the data-service.

Each module provides a dual-mode store:
  - In-memory (when USE_MOCK=True or IS_LOCAL=True) for local dev and testing.
  - Real boto3 DynamoDB calls in production.
"""

from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation
from typing import Any


def sanitize_for_dynamodb(obj: Any) -> Any:
    """Recursively convert float → Decimal for DynamoDB boto3 compatibility.

    DynamoDB's boto3 SDK raises TypeError on Python float values; Decimal is required.
    NaN/Inf are not supported by DynamoDB and are converted to their string representations.
    """
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return str(obj)
        try:
            return Decimal(str(obj))
        except InvalidOperation:
            return str(obj)
    if isinstance(obj, dict):
        return {k: sanitize_for_dynamodb(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_dynamodb(v) for v in obj]
    return obj
