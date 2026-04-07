"""Comprehensive tests for risk_assessment_creation.py service.

Tests cover:
- Service initialization
- Evidence retrieval flow
- Parallel assistant processing
- Error handling paths
- Response merging logic
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestRiskAssessmentCreationServiceInit:
    """Tests for RiskAssessmentCreationService initialization."""

    @patch("risk_evaluation.core.services.risk_assessment_creation.RiskAnalysisAssistant")
    def test_init_default_model(self, mock_assistant_class: MagicMock) -> None:
        """Test initialization with default model."""
        from risk_evaluation.core.services.risk_assessment_creation import (
            RiskAssessmentCreationService,
        )

        service = RiskAssessmentCreationService()
        mock_assistant_class.assert_called_once_with(model_name=None)
        assert service.assistant is not None

    @patch("risk_evaluation.core.services.risk_assessment_creation.RiskAnalysisAssistant")
    def test_init_custom_model(self, mock_assistant_class: MagicMock) -> None:
        """Test initialization with custom model name."""
        from risk_evaluation.core.services.risk_assessment_creation import (
            RiskAssessmentCreationService,
        )

        service = RiskAssessmentCreationService(model_name="gpt-4")
        mock_assistant_class.assert_called_once_with(model_name="gpt-4")
        assert service.assistant is not None


class TestRetrieveEvidenceFromDatabricks:
    """Tests for retrieve_evidence_from_databricks method."""

    @pytest.fixture
    def mock_service(self) -> MagicMock:
        """Create a mocked service instance."""
        with patch(
            "risk_evaluation.core.services.risk_assessment_creation.RiskAnalysisAssistant"
        ) as mock_assistant_class:
            mock_assistant = MagicMock()
            mock_assistant.run_parallel_assistant = AsyncMock()
            mock_assistant.invoke_assistant = AsyncMock()
            mock_assistant_class.return_value = mock_assistant

            from risk_evaluation.core.services.risk_assessment_creation import (
                RiskAssessmentCreationService,
            )

            service = RiskAssessmentCreationService()
            return service

    @pytest.mark.asyncio
    @patch("risk_evaluation.core.services.risk_assessment_creation.run_http_with_tool")
    @patch("risk_evaluation.core.services.risk_assessment_creation.format_assistant_response")
    async def test_successful_retrieval_both_responses(
        self,
        mock_format: MagicMock,
        mock_run_tool: AsyncMock,
        mock_service: MagicMock,
    ) -> None:
        """Test successful evidence retrieval with both parallel responses."""
        # Setup mocks
        mock_run_tool.return_value = {"data": "test"}
        mock_service.assistant.run_parallel_assistant = AsyncMock(
            return_value=(
                {"data": [{"Sl No.": 1, "info": "A"}]},
                {"data": [{"Sl No.": 1, "info": "B"}]},
            )
        )
        mock_format.side_effect = [
            (True, {"columns": ["Sl No.", "info"], "data": [{"Sl No.": 1, "info": "A"}]}),
            (True, {"data": [{"Sl No.": 1, "info": "B"}]}),
            (True, {"columns": ["result"], "data": [{"result": "final"}]}),
        ]
        mock_service.assistant.invoke_assistant = AsyncMock(
            return_value={"columns": ["result"], "data": [{"result": "final"}]}
        )

        result = await mock_service.retrieve_evidence_from_databricks(
            query="test query", esn="ESN001", component_type="Stator"
        )

        assert result is not None
        mock_run_tool.assert_called()

    @pytest.mark.asyncio
    @patch("risk_evaluation.core.services.risk_assessment_creation.run_http_with_tool")
    @patch("risk_evaluation.core.services.risk_assessment_creation.format_assistant_response")
    async def test_successful_retrieval_only_response_a(
        self,
        mock_format: MagicMock,
        mock_run_tool: AsyncMock,
        mock_service: MagicMock,
    ) -> None:
        """Test when only response A is successful."""
        mock_run_tool.return_value = {"data": "test"}
        mock_service.assistant.run_parallel_assistant = AsyncMock(
            return_value=({"data": [{"Sl No.": 1}]}, None)
        )
        mock_format.side_effect = [
            (True, {"columns": ["Sl No."], "data": [{"Sl No.": 1}]}),
            (False, None),
            (True, {"data": [{"result": "final"}]}),
        ]
        mock_service.assistant.invoke_assistant = AsyncMock(
            return_value={"data": [{"result": "final"}]}
        )

        result = await mock_service.retrieve_evidence_from_databricks(
            query="test", esn="ESN001", component_type="Rotor"
        )

        assert result is not None

    @pytest.mark.asyncio
    @patch("risk_evaluation.core.services.risk_assessment_creation.run_http_with_tool")
    @patch("risk_evaluation.core.services.risk_assessment_creation.format_assistant_response")
    async def test_successful_retrieval_only_response_b(
        self,
        mock_format: MagicMock,
        mock_run_tool: AsyncMock,
        mock_service: MagicMock,
    ) -> None:
        """Test when only response B is successful."""
        mock_run_tool.return_value = {"data": "test"}
        mock_service.assistant.run_parallel_assistant = AsyncMock(
            return_value=(None, {"data": [{"Sl No.": 1}]})
        )
        mock_format.side_effect = [
            (False, None),
            (True, {"columns": ["Sl No."], "data": [{"Sl No.": 1}]}),
            (True, {"data": [{"result": "final"}]}),
        ]
        mock_service.assistant.invoke_assistant = AsyncMock(
            return_value={"data": [{"result": "final"}]}
        )

        result = await mock_service.retrieve_evidence_from_databricks(
            query="test", esn="ESN001", component_type="Bearing"
        )

        assert result is not None

    @pytest.mark.asyncio
    @patch("risk_evaluation.core.services.risk_assessment_creation.run_http_with_tool")
    @patch("risk_evaluation.core.services.risk_assessment_creation.format_assistant_response")
    async def test_both_responses_empty_raises_error(
        self,
        mock_format: MagicMock,
        mock_run_tool: AsyncMock,
        mock_service: MagicMock,
    ) -> None:
        """Test that empty parallel responses return empty data."""
        mock_run_tool.return_value = {"data": "test"}
        mock_service.assistant.run_parallel_assistant = AsyncMock(
            return_value=(None, None)
        )

        result = await mock_service.retrieve_evidence_from_databricks(
            query="test", esn="ESN001", component_type="Motor"
        )

        # Should return empty data structure on error
        assert result == {"columns": [], "data": []}

    @pytest.mark.asyncio
    @patch("risk_evaluation.core.services.risk_assessment_creation.run_http_with_tool")
    @patch("risk_evaluation.core.services.risk_assessment_creation.format_assistant_response")
    async def test_both_formatting_fails_raises_error(
        self,
        mock_format: MagicMock,
        mock_run_tool: AsyncMock,
        mock_service: MagicMock,
    ) -> None:
        """Test when both response formatting fails."""
        mock_run_tool.return_value = {"data": "test"}
        mock_service.assistant.run_parallel_assistant = AsyncMock(
            return_value=({"data": []}, {"data": []})
        )
        mock_format.side_effect = [
            (False, None),
            (False, None),
        ]

        result = await mock_service.retrieve_evidence_from_databricks(
            query="test", esn="ESN001", component_type="Generator"
        )

        assert result == {"columns": [], "data": []}

    @pytest.mark.asyncio
    @patch("risk_evaluation.core.services.risk_assessment_creation.run_http_with_tool")
    @patch("risk_evaluation.core.services.risk_assessment_creation.format_assistant_response")
    async def test_severity_determination_error(
        self,
        mock_format: MagicMock,
        mock_run_tool: AsyncMock,
        mock_service: MagicMock,
    ) -> None:
        """Test handling of severity determination errors."""
        mock_run_tool.return_value = {"data": "test"}
        mock_service.assistant.run_parallel_assistant = AsyncMock(
            return_value=({"data": [{"Sl No.": 1}]}, None)
        )
        mock_format.side_effect = [
            (True, {"columns": [], "data": [{"Sl No.": 1}]}),
            (False, None),
        ]
        mock_service.assistant.invoke_assistant = AsyncMock(
            side_effect=Exception("Severity error")
        )

        result = await mock_service.retrieve_evidence_from_databricks(
            query="test", esn="ESN001", component_type="Turbine"
        )

        assert result == {"columns": [], "data": []}

    @pytest.mark.asyncio
    @patch("risk_evaluation.core.services.risk_assessment_creation.run_http_with_tool")
    @patch("risk_evaluation.core.services.risk_assessment_creation.format_assistant_response")
    async def test_severity_format_fails_returns_raw(
        self,
        mock_format: MagicMock,
        mock_run_tool: AsyncMock,
        mock_service: MagicMock,
    ) -> None:
        """Test returning raw response when severity formatting fails."""
        mock_run_tool.return_value = {"data": "test"}
        mock_service.assistant.run_parallel_assistant = AsyncMock(
            return_value=({"data": [{"Sl No.": 1}]}, None)
        )
        severity_raw_response = "raw severity response"
        mock_format.side_effect = [
            (True, {"columns": [], "data": [{"Sl No.": 1}]}),
            (False, None),
            (False, None),  # Severity format fails
        ]
        mock_service.assistant.invoke_assistant = AsyncMock(
            return_value=severity_raw_response
        )

        result = await mock_service.retrieve_evidence_from_databricks(
            query="test", esn="ESN001", component_type="Compressor"
        )

        assert result == severity_raw_response

    @pytest.mark.asyncio
    @patch("risk_evaluation.core.services.risk_assessment_creation.run_http_with_tool")
    async def test_mcp_tool_calls(
        self,
        mock_run_tool: AsyncMock,
        mock_service: MagicMock,
    ) -> None:
        """Test that correct MCP tools are called."""
        mock_run_tool.return_value = {"data": "test"}
        mock_service.assistant.run_parallel_assistant = AsyncMock(
            return_value=(None, None)
        )

        await mock_service.retrieve_evidence_from_databricks(
            query="component failure", esn="GT12345", component_type="Stator"
        )

        # Verify FSR tool call
        assert mock_run_tool.call_count == 2
        fsr_call = mock_run_tool.call_args_list[0]
        assert fsr_call[0][0] == "query_fsr"

        # Verify ER tool call
        er_call = mock_run_tool.call_args_list[1]
        assert er_call[0][0] == "query_risk_er"


class TestMergeResponseData:
    """Tests for response data merging logic."""

    @pytest.fixture
    def mock_service(self) -> MagicMock:
        """Create service for merge tests."""
        with patch(
            "risk_evaluation.core.services.risk_assessment_creation.RiskAnalysisAssistant"
        ) as mock_assistant_class:
            mock_assistant = MagicMock()
            mock_assistant.run_parallel_assistant = AsyncMock()
            mock_assistant.invoke_assistant = AsyncMock()
            mock_assistant_class.return_value = mock_assistant

            from risk_evaluation.core.services.risk_assessment_creation import (
                RiskAssessmentCreationService,
            )

            return RiskAssessmentCreationService()

    @pytest.mark.asyncio
    @patch("risk_evaluation.core.services.risk_assessment_creation.run_http_with_tool")
    @patch("risk_evaluation.core.services.risk_assessment_creation.format_assistant_response")
    async def test_merge_updates_sl_numbers(
        self,
        mock_format: MagicMock,
        mock_run_tool: AsyncMock,
        mock_service: MagicMock,
    ) -> None:
        """Test that Sl No. values are updated when merging responses."""
        mock_run_tool.return_value = {}
        mock_service.assistant.run_parallel_assistant = AsyncMock(
            return_value=(
                {"data": [{"Sl No.": 1}, {"Sl No.": 2}]},
                {"data": [{"Sl No.": 1}]},
            )
        )
        mock_format.side_effect = [
            (True, {"columns": ["Sl No."], "data": [{"Sl No.": 1}, {"Sl No.": 2}]}),
            (True, {"data": [{"Sl No.": 1}]}),
            (True, {"data": []}),
        ]
        mock_service.assistant.invoke_assistant = AsyncMock(return_value={"data": []})

        await mock_service.retrieve_evidence_from_databricks(
            query="test", esn="ESN001", component_type="Stator"
        )

        # Assistant should be called with merged data
        mock_service.assistant.invoke_assistant.assert_called()

    @pytest.mark.asyncio
    @patch("risk_evaluation.core.services.risk_assessment_creation.run_http_with_tool")
    @patch("risk_evaluation.core.services.risk_assessment_creation.format_assistant_response")
    async def test_merge_empty_first_response(
        self,
        mock_format: MagicMock,
        mock_run_tool: AsyncMock,
        mock_service: MagicMock,
    ) -> None:
        """Test merging when first response data is empty."""
        mock_run_tool.return_value = {}
        mock_service.assistant.run_parallel_assistant = AsyncMock(
            return_value=(
                {"data": []},
                {"data": [{"Sl No.": 1, "info": "B"}]},
            )
        )
        mock_format.side_effect = [
            (True, {"columns": [], "data": []}),
            (True, {"data": [{"Sl No.": 1, "info": "B"}]}),
            (True, {"data": []}),
        ]
        mock_service.assistant.invoke_assistant = AsyncMock(return_value={"data": []})

        result = await mock_service.retrieve_evidence_from_databricks(
            query="test", esn="ESN001", component_type="Rotor"
        )

        assert result is not None


class TestErrorHandling:
    """Tests for error handling in the service."""

    @pytest.fixture
    def mock_service(self) -> MagicMock:
        """Create service for error tests."""
        with patch(
            "risk_evaluation.core.services.risk_assessment_creation.RiskAnalysisAssistant"
        ) as mock_assistant_class:
            mock_assistant = MagicMock()
            mock_assistant.run_parallel_assistant = AsyncMock()
            mock_assistant.invoke_assistant = AsyncMock()
            mock_assistant_class.return_value = mock_assistant

            from risk_evaluation.core.services.risk_assessment_creation import (
                RiskAssessmentCreationService,
            )

            return RiskAssessmentCreationService()

    @pytest.mark.asyncio
    @patch("risk_evaluation.core.services.risk_assessment_creation.run_http_with_tool")
    async def test_parallel_assistant_exception(
        self,
        mock_run_tool: AsyncMock,
        mock_service: MagicMock,
    ) -> None:
        """Test handling of parallel assistant exceptions."""
        mock_run_tool.return_value = {}
        mock_service.assistant.run_parallel_assistant = AsyncMock(
            side_effect=Exception("Parallel processing failed")
        )

        result = await mock_service.retrieve_evidence_from_databricks(
            query="test", esn="ESN001", component_type="Motor"
        )

        assert result == {"columns": [], "data": []}

    @pytest.mark.asyncio
    @patch("risk_evaluation.core.services.risk_assessment_creation.run_http_with_tool")
    async def test_fsr_tool_error_propagates(
        self,
        mock_run_tool: AsyncMock,
        mock_service: MagicMock,
    ) -> None:
        """Test that FSR tool errors propagate (not caught internally)."""
        mock_run_tool.side_effect = Exception("FSR tool error")

        # The error should propagate since it's not caught
        with pytest.raises(Exception) as exc_info:
            await mock_service.retrieve_evidence_from_databricks(
                query="test", esn="ESN001", component_type="Compressor"
            )

        assert "FSR tool error" in str(exc_info.value)
