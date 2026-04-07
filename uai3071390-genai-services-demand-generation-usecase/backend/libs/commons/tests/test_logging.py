"""Tests for commons.logging stub.

Only the stable public API surface is tested here so that the suite
continues to pass when the body of ``get_logger`` is swapped for the
platform implementation.
"""

from __future__ import annotations

import logging

import pytest

from commons.logging import get_logger


def test_get_logger_returns_logger() -> None:
    logger = get_logger("test.returns_logger")
    assert isinstance(logger, logging.Logger)


def test_get_logger_returns_same_instance() -> None:
    a = get_logger("test.singleton")
    b = get_logger("test.singleton")
    assert a is b


def test_get_logger_does_not_duplicate_handlers() -> None:
    """Verify multiple get_logger calls don't add duplicate handlers.
    
    The current implementation relies on propagation to root logger
    and doesn't add handlers directly to child loggers.
    """
    name = "test.no_dup"
    get_logger(name)
    initial_count = len(logging.getLogger(name).handlers)
    get_logger(name)
    get_logger(name)
    # Call multiple times should not add handlers
    assert len(logging.getLogger(name).handlers) == initial_count


def test_default_level_is_info() -> None:
    logger = get_logger("test.default_level")
    assert logger.level == logging.INFO


def test_custom_level_applied() -> None:
    logger = get_logger("test.custom_level", level=logging.DEBUG)
    assert logger.level == logging.DEBUG


@pytest.mark.parametrize("level", [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR])
def test_can_log_at_all_levels(level: int) -> None:
    logger = get_logger(f"test.level_{level}")
    logger.setLevel(logging.DEBUG)
    # Just verify no exception is raised.
    logger.log(level, "level test message")


def test_level_filtering_suppresses_low_level(capfd: pytest.CaptureFixture[str]) -> None:
    logger = get_logger("test.filter_suppress")
    # Use a direct handler here so the test is isolated from root logger state.
    logger.handlers.clear()
    import sys

    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)
    logger.propagate = False
    logger.setLevel(logging.WARNING)
    logger.debug("should be suppressed")
    captured = capfd.readouterr()
    assert "should be suppressed" not in captured.out
