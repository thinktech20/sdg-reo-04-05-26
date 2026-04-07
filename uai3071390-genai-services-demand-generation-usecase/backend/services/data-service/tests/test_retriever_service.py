"""Tests for the Retriever Service (FSR semantic search).

Tests cover:
- Input validation (query, top_k)
- Databricks configuration validation
- Vector search execution and error handling
- Score gap filtering logic
- Result formatting
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from data_service.services.retriever_service import (
    RetrieverServiceError,
    retrieve_issue_data,
)

# ---------------------------------------------------------------------------
# RetrieverServiceError Tests
# ---------------------------------------------------------------------------


class TestRetrieverServiceError:
    """Tests for RetrieverServiceError exception class."""

    def test_error_with_default_code(self) -> None:
        error = RetrieverServiceError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.error_code == "RETRIEVER_ERROR"

    def test_error_with_custom_code(self) -> None:
        error = RetrieverServiceError("Connection failed", error_code="CONNECTION_ERROR")
        assert str(error) == "Connection failed"
        assert error.message == "Connection failed"
        assert error.error_code == "CONNECTION_ERROR"

    def test_error_is_exception(self) -> None:
        error = RetrieverServiceError("Test")
        assert isinstance(error, Exception)


# ---------------------------------------------------------------------------
# Input Validation Tests
# ---------------------------------------------------------------------------


class TestInputValidation:
    """Tests for input validation in retrieve_issue_data."""

    @pytest.mark.asyncio
    async def test_empty_query_returns_error(self) -> None:
        result = await retrieve_issue_data(query="")
        data = json.loads(result)
        assert data["error"] == "Query is required for FSR analysis"
        assert data["data"] == []

    @pytest.mark.asyncio
    async def test_whitespace_only_query_returns_error(self) -> None:
        result = await retrieve_issue_data(query="   ")
        data = json.loads(result)
        assert data["error"] == "Query is required for FSR analysis"
        assert data["data"] == []

    @pytest.mark.asyncio
    async def test_none_query_returns_error(self) -> None:
        result = await retrieve_issue_data(query=None)  # type: ignore[arg-type]
        data = json.loads(result)
        assert data["error"] == "Query is required for FSR analysis"

    @pytest.mark.asyncio
    async def test_top_k_below_minimum_returns_error(self) -> None:
        result = await retrieve_issue_data(query="test query", top_k=0)
        data = json.loads(result)
        assert data["error"] == "top_k must be between 1 and 20"
        assert data["data"] == []

    @pytest.mark.asyncio
    async def test_top_k_above_maximum_returns_error(self) -> None:
        result = await retrieve_issue_data(query="test query", top_k=21)
        data = json.loads(result)
        assert data["error"] == "top_k must be between 1 and 20"
        assert data["data"] == []

    @pytest.mark.asyncio
    async def test_top_k_at_minimum_is_valid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Set all required env vars so we get past validation to Databricks import
        monkeypatch.setenv("DATABRICKS_WORKSPACE_URL", "https://test.databricks.com")
        monkeypatch.setenv("DATABRICKS_TOKEN", "test-token")
        monkeypatch.setenv("VECTOR_SEARCH_ENDPOINT", "test-endpoint")
        monkeypatch.setenv("VECTOR_SEARCH_INDEX", "test-index")

        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_index = MagicMock()
            mock_index.similarity_search.return_value = {"result": {"data_array": []}}
            mock_client.return_value.get_index.return_value = mock_index

            result = await retrieve_issue_data(query="test", top_k=1)
            data = json.loads(result)
            # Should not contain error about top_k
            assert "error" not in data or "top_k" not in data.get("error", "")

    @pytest.mark.asyncio
    async def test_top_k_at_maximum_is_valid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABRICKS_WORKSPACE_URL", "https://test.databricks.com")
        monkeypatch.setenv("DATABRICKS_TOKEN", "test-token")
        monkeypatch.setenv("VECTOR_SEARCH_ENDPOINT", "test-endpoint")
        monkeypatch.setenv("VECTOR_SEARCH_INDEX", "test-index")

        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_index = MagicMock()
            mock_index.similarity_search.return_value = {"result": {"data_array": []}}
            mock_client.return_value.get_index.return_value = mock_index

            result = await retrieve_issue_data(query="test", top_k=20)
            data = json.loads(result)
            assert "error" not in data or "top_k" not in data.get("error", "")


# ---------------------------------------------------------------------------
# Configuration Validation Tests
# ---------------------------------------------------------------------------


class TestConfigValidation:
    """Tests for Databricks configuration validation."""

    @pytest.mark.asyncio
    async def test_missing_workspace_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DATABRICKS_WORKSPACE_URL", raising=False)
        monkeypatch.setenv("DATABRICKS_TOKEN", "test-token")
        monkeypatch.setenv("VECTOR_SEARCH_ENDPOINT", "test-endpoint")
        monkeypatch.setenv("VECTOR_SEARCH_INDEX", "test-index")

        with patch.dict("data_service.services.retriever_service.os.environ", {
            "DATABRICKS_TOKEN": "test-token",
            "VECTOR_SEARCH_ENDPOINT": "test-endpoint",
            "VECTOR_SEARCH_INDEX": "test-index",
        }, clear=True):
            result = await retrieve_issue_data(query="test query")
            data = json.loads(result)
            assert "error" in data
            assert "Missing required Databricks config" in data["error"]
            assert "workspace_url" in data["error"]

    @pytest.mark.asyncio
    async def test_missing_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with patch.dict("data_service.services.retriever_service.os.environ", {
            "DATABRICKS_WORKSPACE_URL": "https://test.databricks.com",
            "VECTOR_SEARCH_ENDPOINT": "test-endpoint",
            "VECTOR_SEARCH_INDEX": "test-index",
        }, clear=True):
            result = await retrieve_issue_data(query="test query")
            data = json.loads(result)
            assert "error" in data
            assert "Missing required Databricks config" in data["error"]

    @pytest.mark.asyncio
    async def test_missing_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with patch.dict("data_service.services.retriever_service.os.environ", {
            "DATABRICKS_WORKSPACE_URL": "https://test.databricks.com",
            "DATABRICKS_TOKEN": "test-token",
            "VECTOR_SEARCH_INDEX": "test-index",
        }, clear=True):
            result = await retrieve_issue_data(query="test query")
            data = json.loads(result)
            assert "error" in data
            assert "Missing required Databricks config" in data["error"]

    @pytest.mark.asyncio
    async def test_missing_index(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with patch.dict("data_service.services.retriever_service.os.environ", {
            "DATABRICKS_WORKSPACE_URL": "https://test.databricks.com",
            "DATABRICKS_TOKEN": "test-token",
            "VECTOR_SEARCH_ENDPOINT": "test-endpoint",
        }, clear=True):
            result = await retrieve_issue_data(query="test query")
            data = json.loads(result)
            assert "error" in data
            assert "Missing required Databricks config" in data["error"]


# ---------------------------------------------------------------------------
# Databricks Connection and Search Tests
# ---------------------------------------------------------------------------


class TestDatabricksConnection:
    """Tests for Databricks connection handling."""

    @pytest.fixture
    def mock_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set up required environment variables."""
        monkeypatch.setenv("DATABRICKS_WORKSPACE_URL", "https://test.databricks.com")
        monkeypatch.setenv("DATABRICKS_TOKEN", "test-token")
        monkeypatch.setenv("VECTOR_SEARCH_ENDPOINT", "test-endpoint")
        monkeypatch.setenv("VECTOR_SEARCH_INDEX", "test-index")

    @pytest.mark.asyncio
    async def test_connection_error(self, mock_env: None) -> None:
        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_client.return_value.get_index.side_effect = Exception("Connection refused")

            result = await retrieve_issue_data(query="test query")
            data = json.loads(result)

            assert "error" in data
            assert "Failed to connect to Databricks index" in data["error"]
            assert data["data"] == []

    @pytest.mark.asyncio
    async def test_vector_search_error(self, mock_env: None) -> None:
        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_index = MagicMock()
            mock_index.similarity_search.side_effect = Exception("Search timeout")
            mock_client.return_value.get_index.return_value = mock_index

            result = await retrieve_issue_data(query="test query")
            data = json.loads(result)

            assert "error" in data
            assert "Vector search failed" in data["error"]
            assert data["data"] == []

    @pytest.mark.asyncio
    async def test_databricks_sdk_not_installed(self, mock_env: None) -> None:
        with patch.dict("sys.modules", {"databricks.vector_search.client": None}):
            with patch("databricks.vector_search.client.VectorSearchClient", side_effect=ImportError("No module")):
                # The actual behavior when the import fails in the try block
                result = await retrieve_issue_data(query="test query")
                data = json.loads(result)

                assert "error" in data
                assert data["data"] == []


# ---------------------------------------------------------------------------
# Successful Search Tests
# ---------------------------------------------------------------------------


class TestSuccessfulSearch:
    """Tests for successful vector search scenarios."""

    @pytest.fixture
    def mock_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set up required environment variables."""
        monkeypatch.setenv("DATABRICKS_WORKSPACE_URL", "https://test.databricks.com")
        monkeypatch.setenv("DATABRICKS_TOKEN", "test-token")
        monkeypatch.setenv("VECTOR_SEARCH_ENDPOINT", "test-endpoint")
        monkeypatch.setenv("VECTOR_SEARCH_INDEX", "test-index")
        monkeypatch.setenv("SIMILARITY_SCORE_DELTA", "0.025")

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_env: None) -> None:
        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_index = MagicMock()
            mock_index.similarity_search.return_value = {"result": {"data_array": []}}
            mock_client.return_value.get_index.return_value = mock_index

            result = await retrieve_issue_data(query="test query")
            data = json.loads(result)

            assert "error" not in data
            assert data["data"] == []

    @pytest.mark.asyncio
    async def test_single_result(self, mock_env: None) -> None:
        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_index = MagicMock()
            mock_index.similarity_search.return_value = {
                "result": {
                    "data_array": [
                        ["Evidence text here", "Document.pdf", 5, "2024-01-15", 0.95]
                    ]
                }
            }
            mock_client.return_value.get_index.return_value = mock_index

            result = await retrieve_issue_data(query="DC leakage test")
            data = json.loads(result)

            assert "error" not in data
            assert len(data["data"]) == 1
            assert data["data"][0]["#"] == 1
            assert data["data"][0]["Evidence"] == "Evidence text here"
            assert data["data"][0]["Document Name"] == "Document.pdf"
            assert data["data"][0]["Page Number"] == 5
            assert data["data"][0]["Report Date"] == "2024-01-15"

    @pytest.mark.asyncio
    async def test_multiple_results(self, mock_env: None) -> None:
        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_index = MagicMock()
            mock_index.similarity_search.return_value = {
                "result": {
                    "data_array": [
                        ["First evidence", "Doc1.pdf", 1, "2024-01-01", 0.95],
                        ["Second evidence", "Doc2.pdf", 2, "2024-01-02", 0.94],
                        ["Third evidence", "Doc3.pdf", 3, "2024-01-03", 0.93],
                    ]
                }
            }
            mock_client.return_value.get_index.return_value = mock_index

            result = await retrieve_issue_data(query="test query")
            data = json.loads(result)

            assert len(data["data"]) == 3
            assert data["data"][0]["#"] == 1
            assert data["data"][1]["#"] == 2
            assert data["data"][2]["#"] == 3

    @pytest.mark.asyncio
    async def test_filters_by_esn(self, mock_env: None) -> None:
        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_index = MagicMock()
            mock_index.similarity_search.return_value = {"result": {"data_array": []}}
            mock_client.return_value.get_index.return_value = mock_index

            await retrieve_issue_data(query="test", esn="ESN12345")

            # Verify filter was passed to similarity_search
            call_args = mock_index.similarity_search.call_args
            assert call_args.kwargs["filters"] == {"generator_serial": "ESN12345"}

    @pytest.mark.asyncio
    async def test_no_filter_when_esn_is_none(self, mock_env: None) -> None:
        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_index = MagicMock()
            mock_index.similarity_search.return_value = {"result": {"data_array": []}}
            mock_client.return_value.get_index.return_value = mock_index

            await retrieve_issue_data(query="test")

            call_args = mock_index.similarity_search.call_args
            assert call_args.kwargs["filters"] is None

    @pytest.mark.asyncio
    async def test_component_type_added_to_query(self, mock_env: None) -> None:
        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_index = MagicMock()
            mock_index.similarity_search.return_value = {"result": {"data_array": []}}
            mock_client.return_value.get_index.return_value = mock_index

            await retrieve_issue_data(query="test query", component_type="Stator")

            call_args = mock_index.similarity_search.call_args
            assert call_args.kwargs["query_text"] == "Stator: test query"

    @pytest.mark.asyncio
    async def test_query_without_component_type(self, mock_env: None) -> None:
        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_index = MagicMock()
            mock_index.similarity_search.return_value = {"result": {"data_array": []}}
            mock_client.return_value.get_index.return_value = mock_index

            await retrieve_issue_data(query="test query", component_type=None)

            call_args = mock_index.similarity_search.call_args
            assert call_args.kwargs["query_text"] == "test query"


# ---------------------------------------------------------------------------
# Score Gap Filtering Tests
# ---------------------------------------------------------------------------


class TestScoreGapFiltering:
    """Tests for similarity score gap filtering logic."""

    @pytest.fixture
    def mock_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set up required environment variables."""
        monkeypatch.setenv("DATABRICKS_WORKSPACE_URL", "https://test.databricks.com")
        monkeypatch.setenv("DATABRICKS_TOKEN", "test-token")
        monkeypatch.setenv("VECTOR_SEARCH_ENDPOINT", "test-endpoint")
        monkeypatch.setenv("VECTOR_SEARCH_INDEX", "test-index")

    @pytest.mark.asyncio
    async def test_score_gap_stops_at_large_gap(self, mock_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        # Set delta to 0.03 - gaps smaller than this will pass, larger will stop
        monkeypatch.setenv("SIMILARITY_SCORE_DELTA", "0.03")

        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_index = MagicMock()
            # Results with small gaps first, then a big gap
            mock_index.similarity_search.return_value = {
                "result": {
                    "data_array": [
                        ["Evidence 1", "Doc1.pdf", 1, "2024-01-01", 0.95],
                        ["Evidence 2", "Doc2.pdf", 2, "2024-01-02", 0.93],  # Gap: 0.02 < 0.03, OK
                        ["Evidence 3", "Doc3.pdf", 3, "2024-01-03", 0.85],  # Gap: 0.08 > 0.03, STOP
                        ["Evidence 4", "Doc4.pdf", 4, "2024-01-04", 0.84],
                    ]
                }
            }
            mock_client.return_value.get_index.return_value = mock_index

            result = await retrieve_issue_data(query="test query")
            data = json.loads(result)

            # Should stop after result 2 due to score gap (0.93 -> 0.85 = 0.08 > 0.03)
            assert len(data["data"]) == 2
            assert data["data"][0]["Evidence"] == "Evidence 1"
            assert data["data"][1]["Evidence"] == "Evidence 2"

    @pytest.mark.asyncio
    async def test_score_gap_includes_all_when_small_gaps(self, mock_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SIMILARITY_SCORE_DELTA", "0.05")

        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_index = MagicMock()
            # Results with small gaps (0.01 each)
            mock_index.similarity_search.return_value = {
                "result": {
                    "data_array": [
                        ["Evidence 1", "Doc1.pdf", 1, "2024-01-01", 0.95],
                        ["Evidence 2", "Doc2.pdf", 2, "2024-01-02", 0.94],
                        ["Evidence 3", "Doc3.pdf", 3, "2024-01-03", 0.93],
                    ]
                }
            }
            mock_client.return_value.get_index.return_value = mock_index

            result = await retrieve_issue_data(query="test query")
            data = json.loads(result)

            # All results included since gaps are smaller than delta
            assert len(data["data"]) == 3

    @pytest.mark.asyncio
    async def test_max_10_results_processed(self, mock_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SIMILARITY_SCORE_DELTA", "1.0")  # High delta to not trigger gap filter

        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_index = MagicMock()
            # 15 results - should cap at 10
            mock_index.similarity_search.return_value = {
                "result": {
                    "data_array": [
                        [f"Evidence {i}", f"Doc{i}.pdf", i, "2024-01-01", 0.95 - (i * 0.001)]
                        for i in range(15)
                    ]
                }
            }
            mock_client.return_value.get_index.return_value = mock_index

            result = await retrieve_issue_data(query="test query")
            data = json.loads(result)

            # Maximum 10 results returned
            assert len(data["data"]) == 10

    @pytest.mark.asyncio
    async def test_handles_missing_score_data(self, mock_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SIMILARITY_SCORE_DELTA", "0.025")

        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_index = MagicMock()
            # Results with missing score (index 4)
            mock_index.similarity_search.return_value = {
                "result": {
                    "data_array": [
                        ["Evidence 1", "Doc1.pdf", 1, "2024-01-01"],  # No score
                        ["Evidence 2", "Doc2.pdf", 2, "2024-01-02", None],  # None score
                    ]
                }
            }
            mock_client.return_value.get_index.return_value = mock_index

            result = await retrieve_issue_data(query="test query")
            data = json.loads(result)

            # Should handle gracefully
            assert len(data["data"]) >= 1

    @pytest.mark.asyncio
    async def test_handles_partial_row_data(self, mock_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SIMILARITY_SCORE_DELTA", "0.025")

        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_index = MagicMock()
            # Row with only partial data
            mock_index.similarity_search.return_value = {
                "result": {
                    "data_array": [
                        ["Evidence only"],  # Only first field
                    ]
                }
            }
            mock_client.return_value.get_index.return_value = mock_index

            result = await retrieve_issue_data(query="test query")
            data = json.loads(result)

            assert len(data["data"]) == 1
            assert data["data"][0]["Evidence"] == "Evidence only"
            assert data["data"][0]["Document Name"] == ""
            assert data["data"][0]["Page Number"] == ""
            assert data["data"][0]["Report Date"] == ""


# ---------------------------------------------------------------------------
# Input Sanitization Tests
# ---------------------------------------------------------------------------


class TestInputSanitization:
    """Tests for input sanitization."""

    @pytest.fixture
    def mock_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABRICKS_WORKSPACE_URL", "https://test.databricks.com")
        monkeypatch.setenv("DATABRICKS_TOKEN", "test-token")
        monkeypatch.setenv("VECTOR_SEARCH_ENDPOINT", "test-endpoint")
        monkeypatch.setenv("VECTOR_SEARCH_INDEX", "test-index")

    @pytest.mark.asyncio
    async def test_strips_whitespace_from_query(self, mock_env: None) -> None:
        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_index = MagicMock()
            mock_index.similarity_search.return_value = {"result": {"data_array": []}}
            mock_client.return_value.get_index.return_value = mock_index

            await retrieve_issue_data(query="  test query  ")

            call_args = mock_index.similarity_search.call_args
            # Query should be stripped (though component_type prefix may be added)
            assert "test query" in call_args.kwargs["query_text"]

    @pytest.mark.asyncio
    async def test_strips_whitespace_from_esn(self, mock_env: None) -> None:
        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_index = MagicMock()
            mock_index.similarity_search.return_value = {"result": {"data_array": []}}
            mock_client.return_value.get_index.return_value = mock_index

            await retrieve_issue_data(query="test", esn="  ESN123  ")

            call_args = mock_index.similarity_search.call_args
            assert call_args.kwargs["filters"] == {"generator_serial": "ESN123"}

    @pytest.mark.asyncio
    async def test_empty_esn_becomes_none(self, mock_env: None) -> None:
        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_index = MagicMock()
            mock_index.similarity_search.return_value = {"result": {"data_array": []}}
            mock_client.return_value.get_index.return_value = mock_index

            await retrieve_issue_data(query="test", esn="   ")

            call_args = mock_index.similarity_search.call_args
            assert call_args.kwargs["filters"] is None

    @pytest.mark.asyncio
    async def test_strips_whitespace_from_component_type(self, mock_env: None) -> None:
        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_index = MagicMock()
            mock_index.similarity_search.return_value = {"result": {"data_array": []}}
            mock_client.return_value.get_index.return_value = mock_index

            await retrieve_issue_data(query="test", component_type="  Stator  ")

            call_args = mock_index.similarity_search.call_args
            assert call_args.kwargs["query_text"] == "Stator: test"

    @pytest.mark.asyncio
    async def test_empty_component_type_not_added_to_query(self, mock_env: None) -> None:
        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_index = MagicMock()
            mock_index.similarity_search.return_value = {"result": {"data_array": []}}
            mock_client.return_value.get_index.return_value = mock_index

            await retrieve_issue_data(query="test", component_type="   ")

            call_args = mock_index.similarity_search.call_args
            assert call_args.kwargs["query_text"] == "test"


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.fixture
    def mock_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABRICKS_WORKSPACE_URL", "https://test.databricks.com")
        monkeypatch.setenv("DATABRICKS_TOKEN", "test-token")
        monkeypatch.setenv("VECTOR_SEARCH_ENDPOINT", "test-endpoint")
        monkeypatch.setenv("VECTOR_SEARCH_INDEX", "test-index")
        monkeypatch.setenv("SIMILARITY_SCORE_DELTA", "0.025")

    @pytest.mark.asyncio
    async def test_result_missing_nested_structure(self, mock_env: None) -> None:
        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_index = MagicMock()
            # Missing 'result' key
            mock_index.similarity_search.return_value = {}
            mock_client.return_value.get_index.return_value = mock_index

            result = await retrieve_issue_data(query="test")
            data = json.loads(result)

            assert data["data"] == []

    @pytest.mark.asyncio
    async def test_result_missing_data_array(self, mock_env: None) -> None:
        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_index = MagicMock()
            # Has 'result' but no 'data_array'
            mock_index.similarity_search.return_value = {"result": {}}
            mock_client.return_value.get_index.return_value = mock_index

            result = await retrieve_issue_data(query="test")
            data = json.loads(result)

            assert data["data"] == []

    @pytest.mark.asyncio
    async def test_general_exception_handling(self, mock_env: None) -> None:
        with patch("databricks.vector_search.client.VectorSearchClient") as mock_client:
            mock_client.side_effect = RuntimeError("Unexpected error")

            result = await retrieve_issue_data(query="test")
            data = json.loads(result)

            assert "error" in data
            assert "Databricks retrieval failed" in data["error"]
            assert data["data"] == []
