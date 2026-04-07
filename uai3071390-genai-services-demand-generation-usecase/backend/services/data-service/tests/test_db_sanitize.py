"""Unit tests for data_service.db.sanitize_for_dynamodb.

Covers the float → Decimal conversion and 400KB-limit helper introduced in
bugfix/622621-ddb-payload.
"""

from __future__ import annotations

import math
from decimal import Decimal

import pytest

from data_service.db import sanitize_for_dynamodb


class TestSanitizeForDynamoDB:
    # ------------------------------------------------------------------
    # Scalar conversions
    # ------------------------------------------------------------------

    def test_regular_float_becomes_decimal(self) -> None:
        result = sanitize_for_dynamodb(1.5)
        assert isinstance(result, Decimal)
        assert result == Decimal("1.5")

    def test_float_zero_becomes_decimal(self) -> None:
        result = sanitize_for_dynamodb(0.0)
        assert result == Decimal("0.0")

    def test_negative_float_becomes_decimal(self) -> None:
        result = sanitize_for_dynamodb(-3.14)
        assert isinstance(result, Decimal)

    def test_nan_becomes_string(self) -> None:
        result = sanitize_for_dynamodb(float("nan"))
        assert result == "nan"
        assert isinstance(result, str)

    def test_positive_inf_becomes_string(self) -> None:
        result = sanitize_for_dynamodb(float("inf"))
        assert result == "inf"
        assert isinstance(result, str)

    def test_negative_inf_becomes_string(self) -> None:
        result = sanitize_for_dynamodb(float("-inf"))
        assert result == "-inf"
        assert isinstance(result, str)

    # ------------------------------------------------------------------
    # Non-float types pass through unchanged
    # ------------------------------------------------------------------

    def test_int_passthrough(self) -> None:
        assert sanitize_for_dynamodb(42) == 42
        assert isinstance(sanitize_for_dynamodb(42), int)

    def test_string_passthrough(self) -> None:
        assert sanitize_for_dynamodb("hello") == "hello"

    def test_none_passthrough(self) -> None:
        assert sanitize_for_dynamodb(None) is None

    def test_bool_passthrough(self) -> None:
        # bool is a subclass of int — should NOT be converted
        assert sanitize_for_dynamodb(True) is True
        assert sanitize_for_dynamodb(False) is False

    def test_decimal_passthrough(self) -> None:
        d = Decimal("9.99")
        assert sanitize_for_dynamodb(d) is d

    # ------------------------------------------------------------------
    # Nested structures
    # ------------------------------------------------------------------

    def test_flat_dict_with_float(self) -> None:
        result = sanitize_for_dynamodb({"score": 0.95, "label": "ok"})
        assert isinstance(result["score"], Decimal)
        assert result["label"] == "ok"

    def test_nested_dict(self) -> None:
        data = {"outer": {"inner": 1.1}}
        result = sanitize_for_dynamodb(data)
        assert isinstance(result["outer"]["inner"], Decimal)

    def test_list_of_floats(self) -> None:
        result = sanitize_for_dynamodb([1.0, 2.0, 3.0])
        assert all(isinstance(v, Decimal) for v in result)

    def test_mixed_list(self) -> None:
        result = sanitize_for_dynamodb([1, 2.5, "x", None])
        assert isinstance(result[0], int)
        assert isinstance(result[1], Decimal)
        assert result[2] == "x"
        assert result[3] is None

    def test_deeply_nested(self) -> None:
        data = {"a": [{"b": [{"c": 0.1}]}]}
        result = sanitize_for_dynamodb(data)
        assert isinstance(result["a"][0]["b"][0]["c"], Decimal)

    def test_dict_with_nan_value(self) -> None:
        result = sanitize_for_dynamodb({"v": float("nan")})
        assert result["v"] == "nan"

    def test_empty_dict(self) -> None:
        assert sanitize_for_dynamodb({}) == {}

    def test_empty_list(self) -> None:
        assert sanitize_for_dynamodb([]) == []
