"""Persist risk-analysis results (findings + retrieval) to DynamoDB via data-service."""

from __future__ import annotations

import json
import re
import shutil
import os
from pathlib import Path
from typing import Any

from risk_evaluation.core.config.logger_config import get_logger
from risk_evaluation.core.utils.utils import call_rest_api

logger = get_logger(__name__)


class RiskAnalysisPersistence:
    """Parses LLM results, builds retrieval evidence, and persists both to DynamoDB."""

    def __init__(self, esn: str) -> None:
        self.esn = esn
        self.run_dir = Path(os.getenv("RUN_ARTIFACTS_DIR", "/tmp/run")) / esn

    # ── Parse LLM results ─────────────────────────────────────────────────────

    @staticmethod
    def parse_llm_results(llm_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Parse raw LLM response dicts into structured findings."""
        parsed: list[dict[str, Any]] = []
        for item in llm_results:
            issue_id = item.get("issue_id", "unknown")
            error = item.get("error")
            response_text = item.get("response")

            if error or not response_text:
                parsed.append({
                    "issue_id": issue_id,
                    "findings": [],
                    "summary": f"Error: {error}" if error else "No response",
                })
                continue

            try:
                json_match = re.search(r"```json\s*(.*?)\s*```", str(response_text), re.DOTALL)
                json_str = json_match.group(1) if json_match else str(response_text)
                result = json.loads(json_str)
                result["issue_id"] = issue_id
                parsed.append(result)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning("Failed to parse JSON for issue_id=%s: %s", issue_id, e)
                parsed.append({
                    "issue_id": issue_id,
                    "findings": [],
                    "summary": "Failed to parse LLM response",
                })

        ok = sum(1 for r in parsed if r.get("summary") not in ("No response", "Failed to parse LLM response") and not r.get("summary", "").startswith("Error:"))
        logger.info("Parsed %d/%d LLM results successfully", ok, len(parsed))
        return parsed

    # ── Build retrieval evidence ──────────────────────────────────────────────

    def build_retrieval(self) -> dict[str, dict[str, Any]]:
        """Read fsr_result.json and er_result.json, merge into per-issue retrieval dict."""
        fsr_path = self.run_dir / "fsr_result.json"
        er_path = self.run_dir / "er_result.json"

        fsr_data: dict = {}
        er_data: dict = {}
        
        if fsr_path.exists():
            raw = json.loads(fsr_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                # MCP tool returned a non-dict (e.g. a plain-text error serialised as a
                # JSON string).  Treat as empty — the LLM run still proceeds without FSR evidence.
                logger.warning("fsr_result.json is not a dict (got %s); ignoring FSR retrieval", type(raw).__name__)
            else:
                data = raw.get("data", {})
                fsr_data = data if isinstance(data, dict) else {}
                if not isinstance(data, dict):
                    logger.warning("fsr_result.json 'data' key is not a dict (got %s); ignoring", type(data).__name__)
 
        if er_path.exists():
            raw = json.loads(er_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                logger.warning("er_result.json is not a dict (got %s); ignoring ER retrieval", type(raw).__name__)
            else:
                data = raw.get("data", {})
                er_data = data if isinstance(data, dict) else {}
                if not isinstance(data, dict):
                    logger.warning("er_result.json 'data' key is not a dict (got %s); ignoring", type(data).__name__)

        retrieval: dict[str, dict[str, Any]] = {}
        for issue_id in set(fsr_data.keys()) | set(er_data.keys()):
            retrieval[issue_id] = {
                "fsr_chunks": fsr_data.get(issue_id, []),
                "er_chunks": er_data.get(issue_id, []),
            }
        return retrieval

    # ── Persist to DynamoDB ───────────────────────────────────────────────────

    async def persist(
        self,
        assessment_id: str,
        findings: list[dict[str, Any]],
    ) -> None:
        # Flatten nested LLM output into flat rows before sending.
        # Input format (from parse_llm_results):
        #   [{"findings": [{"Issue name": ..., "Risk": ...}], "summary": "...", "issue_id": "..."}, ...]
        # Required flat format for _sample_rows_to_grouped_findings on the endpoint:
        #   [{"Issue name": ..., "Risk": ..., ...}, {"Issue name": ..., ...}, ...]
        flat_findings: list[dict[str, Any]] = []
        for item in findings:
            inner = item.get("findings")
            if isinstance(inner, list):
                flat_findings.extend(row for row in inner if isinstance(row, dict))
            else:
                # Already a flat row (no nested "findings" key)
                flat_findings.append(item)
 
        logger.info(
            "Flattened %d LLM result items into %d flat finding rows for assessment %s",
            len(findings), len(flat_findings), assessment_id,
        )
 
        # Send flattened findings to the internal risk-eval-sample endpoint.
        # Body matches RiskEvalSamplePersistRequest: assessmentId, esn, payload.
        # The endpoint transforms findings via _sample_rows_to_grouped_findings
        # and delegates to risk_analysis_store.write_risk_analysis.
        await call_rest_api(
            f"/dataservices/api/v1/internal/assessments/{assessment_id}/risk-eval-sample",
            method="POST",
            body={
                "assessmentId": assessment_id,
                "esn": self.esn,
                "payload": {"findings": flat_findings},
            },
        )
        logger.info(
            "Persisted %d findings for assessment %s via risk-eval-sample",
            len(flat_findings), assessment_id,
        )

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def cleanup(self) -> None:
        """Remove the entire ESN run-artifacts folder."""
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)
            logger.info("Deleted ESN folder %s", self.run_dir)
