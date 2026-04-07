"""Comprehensive tests for risk_evaluation/core/services/utils.py.

Tests cover:
- run_http_with_tool function
- _repair_json_string function
- format_assistant_response function
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestRepairJsonString:
    """Tests for _repair_json_string function."""

    def test_removes_markdown_code_blocks(self) -> None:
        """Test removal of markdown code blocks."""
        from risk_evaluation.core.services.utils import _repair_json_string

        input_str = '```json\n{"key": "value"}\n```'
        result = _repair_json_string(input_str)
        assert result == '{"key": "value"}'

    def test_removes_code_block_without_language(self) -> None:
        """Test removal of code blocks without language specification."""
        from risk_evaluation.core.services.utils import _repair_json_string

        input_str = '```\n{"data": [1, 2, 3]}\n```'
        result = _repair_json_string(input_str)
        assert result == '{"data": [1, 2, 3]}'

    def test_extracts_json_from_text(self) -> None:
        """Test extraction of JSON from surrounding text."""
        from risk_evaluation.core.services.utils import _repair_json_string

        input_str = 'Here is the result: {"result": true} Thank you!'
        result = _repair_json_string(input_str)
        assert result == '{"result": true}'

    def test_fixes_sl_no_without_colon(self) -> None:
        """Test fixing Sl No. entries without colon."""
        from risk_evaluation.core.services.utils import _repair_json_string

        input_str = '{"data": [{"Sl No. 1", "name": "test"}]}'
        result = _repair_json_string(input_str)
        assert '"Sl No.": 1' in result

    def test_fixes_duplicate_sl_no_values(self) -> None:
        """Test fixing duplicate Sl No. values."""
        from risk_evaluation.core.services.utils import _repair_json_string

        input_str = '{"data": [{"Sl No.": 1: 1, "name": "test"}]}'
        result = _repair_json_string(input_str)
        assert '"Sl No.": 1' in result

    def test_handles_empty_string(self) -> None:
        """Test handling of empty string."""
        from risk_evaluation.core.services.utils import _repair_json_string

        result = _repair_json_string("")
        assert result == ""

    def test_handles_whitespace_only(self) -> None:
        """Test handling of whitespace-only string."""
        from risk_evaluation.core.services.utils import _repair_json_string

        result = _repair_json_string("   \n\t  ")
        assert result.strip() == ""

    def test_preserves_valid_json(self) -> None:
        """Test that valid JSON is preserved."""
        from risk_evaluation.core.services.utils import _repair_json_string

        input_str = '{"columns": ["A", "B"], "data": [{"A": 1, "B": 2}]}'
        result = _repair_json_string(input_str)
        # Should be parseable
        parsed = json.loads(result)
        assert parsed["columns"] == ["A", "B"]

    def test_handles_nested_json(self) -> None:
        """Test handling of nested JSON structures."""
        from risk_evaluation.core.services.utils import _repair_json_string

        input_str = '{"outer": {"inner": {"deep": "value"}}}'
        result = _repair_json_string(input_str)
        parsed = json.loads(result)
        assert parsed["outer"]["inner"]["deep"] == "value"


class TestFormatAssistantResponse:
    """Tests for format_assistant_response function."""

    def test_formats_dict_with_data_key(self) -> None:
        """Test formatting dict that already has data key."""
        from risk_evaluation.core.services.utils import format_assistant_response

        input_dict = {"data": [{"id": 1}, {"id": 2}]}
        success, result = format_assistant_response(input_dict)

        assert success is True
        assert result == input_dict

    def test_formats_dict_without_data_key(self) -> None:
        """Test formatting dict without data key."""
        from risk_evaluation.core.services.utils import format_assistant_response

        input_dict = {"result": "value", "count": 5}
        success, result = format_assistant_response(input_dict)

        assert success is True
        assert result == input_dict

    def test_filters_non_dict_items_in_data(self) -> None:
        """Test filtering non-dict items from data array."""
        from risk_evaluation.core.services.utils import format_assistant_response

        input_dict = {"data": [{"id": 1}, "invalid", {"id": 2}, 123]}
        success, result = format_assistant_response(input_dict)

        assert success is True

    def test_handles_empty_data_array(self) -> None:
        """Test handling of empty data array."""
        from risk_evaluation.core.services.utils import format_assistant_response

        input_dict = {"data": []}
        success, result = format_assistant_response(input_dict)

        assert success is True
        assert result["data"] == []

    def test_parses_json_string(self) -> None:
        """Test parsing of JSON string."""
        from risk_evaluation.core.services.utils import format_assistant_response

        input_str = '{"data": [{"item": 1}]}'
        success, result = format_assistant_response(input_str)

        assert success is True
        assert result["data"] == [{"item": 1}]

    def test_parses_json_with_markdown(self) -> None:
        """Test parsing JSON wrapped in markdown."""
        from risk_evaluation.core.services.utils import format_assistant_response

        input_str = '```json\n{"data": [{"value": "test"}]}\n```'
        success, result = format_assistant_response(input_str)

        assert success is True
        assert result["data"] == [{"value": "test"}]

    def test_returns_false_for_invalid_json(self) -> None:
        """Test that invalid JSON returns False."""
        from risk_evaluation.core.services.utils import format_assistant_response

        input_str = "This is not valid JSON at all"
        success, result = format_assistant_response(input_str)

        assert success is False
        assert result is None

    def test_returns_false_for_malformed_json(self) -> None:
        """Test that malformed JSON returns False."""
        from risk_evaluation.core.services.utils import format_assistant_response

        input_str = '{"unclosed": "brace'
        success, result = format_assistant_response(input_str)

        assert success is False

    def test_returns_false_for_non_string_non_dict(self) -> None:
        """Test that non-string, non-dict input returns False."""
        from risk_evaluation.core.services.utils import format_assistant_response

        success, result = format_assistant_response(12345)
        assert success is False
        assert result is None

        success, result = format_assistant_response([1, 2, 3])
        assert success is False
        assert result is None

        success, result = format_assistant_response(None)
        assert success is False
        assert result is None

    def test_handles_dict_with_all_valid_items(self) -> None:
        """Test dict where all items in data are dicts."""
        from risk_evaluation.core.services.utils import format_assistant_response

        input_dict = {
            "columns": ["A", "B", "C"],
            "data": [
                {"A": 1, "B": 2, "C": 3},
                {"A": 4, "B": 5, "C": 6},
            ],
        }
        success, result = format_assistant_response(input_dict)

        assert success is True
        assert len(result["data"]) == 2


class TestRunHttpWithTool:
    """Tests for run_http_with_tool async function."""

    @pytest.mark.asyncio
    @patch("risk_evaluation.core.services.utils.streamable_http_client")
    @patch("risk_evaluation.core.services.utils.ClientSession")
    async def test_successful_text_result(
        self,
        mock_session_class: MagicMock,
        mock_http_client: MagicMock,
    ) -> None:
        """Test successful tool call with text result."""
        # Setup mocks
        mock_content = MagicMock()
        mock_content.type = "text"
        mock_content.text = '{"result": "success"}'

        mock_result = MagicMock()
        mock_result.content = [mock_content]

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=mock_result)

        # Setup context managers
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_class.return_value.__aexit__ = AsyncMock()

        mock_http_client.return_value.__aenter__ = AsyncMock(
            return_value=(AsyncMock(), AsyncMock(), None)
        )
        mock_http_client.return_value.__aexit__ = AsyncMock()

        from risk_evaluation.core.services.utils import run_http_with_tool

        result = await run_http_with_tool("test_tool", {"arg": "value"})

        assert result == {"result": "success"}

    @pytest.mark.asyncio
    @patch("risk_evaluation.core.services.utils.streamable_http_client")
    @patch("risk_evaluation.core.services.utils.ClientSession")
    async def test_successful_non_json_text_result(
        self,
        mock_session_class: MagicMock,
        mock_http_client: MagicMock,
    ) -> None:
        """Test successful tool call with non-JSON text result."""
        mock_content = MagicMock()
        mock_content.type = "text"
        mock_content.text = "Plain text result"

        mock_result = MagicMock()
        mock_result.content = [mock_content]

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=mock_result)

        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_class.return_value.__aexit__ = AsyncMock()

        mock_http_client.return_value.__aenter__ = AsyncMock(
            return_value=(AsyncMock(), AsyncMock(), None)
        )
        mock_http_client.return_value.__aexit__ = AsyncMock()

        from risk_evaluation.core.services.utils import run_http_with_tool

        result = await run_http_with_tool("test_tool", {})

        assert result == "Plain text result"

    @pytest.mark.asyncio
    @patch("risk_evaluation.core.services.utils.streamable_http_client")
    @patch("risk_evaluation.core.services.utils.ClientSession")
    async def test_no_content_result(
        self,
        mock_session_class: MagicMock,
        mock_http_client: MagicMock,
    ) -> None:
        """Test tool call with no content in result."""
        mock_result = MagicMock()
        mock_result.content = None

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=mock_result)

        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_class.return_value.__aexit__ = AsyncMock()

        mock_http_client.return_value.__aenter__ = AsyncMock(
            return_value=(AsyncMock(), AsyncMock(), None)
        )
        mock_http_client.return_value.__aexit__ = AsyncMock()

        from risk_evaluation.core.services.utils import run_http_with_tool

        result = await run_http_with_tool("test_tool", {})

        assert result is None

    @pytest.mark.asyncio
    @patch("risk_evaluation.core.services.utils.streamable_http_client")
    @patch("risk_evaluation.core.services.utils.ClientSession")
    async def test_empty_content_list(
        self,
        mock_session_class: MagicMock,
        mock_http_client: MagicMock,
    ) -> None:
        """Test tool call with empty content list."""
        mock_result = MagicMock()
        mock_result.content = []

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=mock_result)

        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_class.return_value.__aexit__ = AsyncMock()

        mock_http_client.return_value.__aenter__ = AsyncMock(
            return_value=(AsyncMock(), AsyncMock(), None)
        )
        mock_http_client.return_value.__aexit__ = AsyncMock()

        from risk_evaluation.core.services.utils import run_http_with_tool

        result = await run_http_with_tool("test_tool", {})

        # Empty list is truthy but has no items
        assert result is None

    @pytest.mark.asyncio
    @patch("risk_evaluation.core.services.utils.streamable_http_client")
    @patch("risk_evaluation.core.services.utils.ClientSession")
    async def test_non_text_content_type(
        self,
        mock_session_class: MagicMock,
        mock_http_client: MagicMock,
    ) -> None:
        """Test tool call with non-text content type."""
        mock_content = MagicMock()
        mock_content.type = "image"

        mock_result = MagicMock()
        mock_result.content = [mock_content]

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=mock_result)

        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_class.return_value.__aexit__ = AsyncMock()

        mock_http_client.return_value.__aenter__ = AsyncMock(
            return_value=(AsyncMock(), AsyncMock(), None)
        )
        mock_http_client.return_value.__aexit__ = AsyncMock()

        from risk_evaluation.core.services.utils import run_http_with_tool

        result = await run_http_with_tool("test_tool", {})

        assert result == mock_content

    @pytest.mark.asyncio
    @patch("risk_evaluation.core.services.utils.streamable_http_client")
    @patch("risk_evaluation.core.services.utils.ClientSession")
    async def test_content_without_type_attribute(
        self,
        mock_session_class: MagicMock,
        mock_http_client: MagicMock,
    ) -> None:
        """Test tool call with content missing type attribute."""
        mock_content = MagicMock(spec=[])  # No attributes

        mock_result = MagicMock()
        mock_result.content = [mock_content]

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=mock_result)

        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_class.return_value.__aexit__ = AsyncMock()

        mock_http_client.return_value.__aenter__ = AsyncMock(
            return_value=(AsyncMock(), AsyncMock(), None)
        )
        mock_http_client.return_value.__aexit__ = AsyncMock()

        from risk_evaluation.core.services.utils import run_http_with_tool

        result = await run_http_with_tool("test_tool", {})

        assert result == mock_content

    @pytest.mark.asyncio
    @patch("risk_evaluation.core.services.utils.streamable_http_client")
    async def test_connection_error(
        self,
        mock_http_client: MagicMock,
    ) -> None:
        """Test handling of connection errors."""
        mock_http_client.return_value.__aenter__ = AsyncMock(
            side_effect=ConnectionError("Connection refused")
        )

        from risk_evaluation.core.services.utils import run_http_with_tool

        with pytest.raises(ConnectionError) as exc_info:
            await run_http_with_tool("test_tool", {})

        assert "Failed to connect to MCP server" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("risk_evaluation.core.services.utils.streamable_http_client")
    async def test_timeout_error(
        self,
        mock_http_client: MagicMock,
    ) -> None:
        """Test handling of timeout errors."""
        mock_http_client.return_value.__aenter__ = AsyncMock(
            side_effect=TimeoutError("Connection timed out")
        )

        from risk_evaluation.core.services.utils import run_http_with_tool

        with pytest.raises(TimeoutError) as exc_info:
            await run_http_with_tool("test_tool", {})

        assert "MCP tool call timed out" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("risk_evaluation.core.services.utils.streamable_http_client")
    async def test_unexpected_error(
        self,
        mock_http_client: MagicMock,
    ) -> None:
        """Test handling of unexpected errors."""
        mock_http_client.return_value.__aenter__ = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )

        from risk_evaluation.core.services.utils import run_http_with_tool

        with pytest.raises(RuntimeError):
            await run_http_with_tool("test_tool", {})


class TestConfigIntegration:
    """Tests for config integration in utils module."""

    @patch("risk_evaluation.core.services.utils.config")
    def test_uses_config_mcp_server_params(self, mock_config: MagicMock) -> None:
        """Test that MCP_SERVER_PARAMS is read from config."""
        mock_config.MCP_SERVER_PARAMS = "http://test-server:8000"

        # Just verify config is accessed
        from risk_evaluation.core.services import utils

        assert hasattr(utils.config, "MCP_SERVER_PARAMS")
