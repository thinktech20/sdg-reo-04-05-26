"""
Risk Assessment Creation Service Module.
Orchestrates MCP tool calls and LLM processing for risk assessment workflows.
"""
import ast
import json
import os
import uuid
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from risk_evaluation.core.agent_factory import AssistantStage, RiskAnalysisAssistant
from risk_evaluation.core.config.logger_config import get_logger
from risk_evaluation.core.utils.utils import call_rest_api, run_http_with_tool
from risk_evaluation.core.utils.prompt_builder import generate_user_prompt_for_LLM

logger = get_logger(__name__)

def _normalize_heatmap_persona(persona: str | None) -> str:
    """Map orchestrator persona values to heatmap service values.
    Orchestrator/assessment flows use RE|OE, while heatmap expects REL|OE.
    """
    normalized = str(persona or "").strip().upper()
    if normalized == "RE":
        return "REL"
    return normalized or "REL"

class RiskAssessmentCreationService:
    """
    Service class for creating risk assessments by calling MCP tools
    and processing results with RiskAnalysisAssistant.
    """

    def __init__(
        self,
        model_name: str | None = None
    ):
        """
        Initialize the Risk Assessment Creation Service.

        Args:
            model_name: The LLM model name (optional, defaults to .env config)
        """
        self.assistant = RiskAnalysisAssistant(
            model_name=model_name
        )
        logger.info("RiskAssessmentCreationService initialized")

    def _save_run_artifact(self, esn: str, filename: str, data: Any) -> None:
        """
        Persist a tool result as a JSON file under the run/<esn>/ directory.

        The directory is created if it does not already exist.
        If the data is not directly JSON-serialisable, non-serialisable values are
        coerced to strings via default=str so the file is always written.

        Args:
            esn:      Equipment serial number — used as the subfolder name.
            filename: Target filename, e.g. "fsr_result.json".
            data:     Python object to serialise (dict, list, str, None, …).
        """
        try:
            # RUN_ARTIFACTS_DIR allows the writable output path to be configured via env var.
            # Default is /tmp/run, which is always writable inside Docker containers.
            run_dir = Path(os.getenv("RUN_ARTIFACTS_DIR", "/tmp/run")) / esn
            # Ensure directory exists in case this is called before _form_esn_issue_matrix
            run_dir.mkdir(parents=True, exist_ok=True)
            artifact_path = run_dir / filename
            with artifact_path.open("w", encoding="utf-8") as fh:
                # default=str handles datetime, UUID, and other non-serialisable types
                json.dump(data, fh, indent=2, ensure_ascii=False, default=str)
            logger.info("Saved run artifact to %s", artifact_path)
        except Exception as e:
            # Non-fatal: log and continue — saving must not block the main flow
            logger.warning("Failed to save run artifact '%s' for esn='%s': %s", filename, esn, e)

    def _form_esn_issue_matrix(self, serial_number: str) -> list[dict]:
        """
        Generate a complete run list for a single serial number with all issue/component combinations.
    
        This method queries the heatmap to retrieve all available issue_name and component combinations,
        then creates a run entry for each combination paired with the provided serial number.
        
        The output format is identical to what _expand_run_list would produce for an entry like:
        {"serial_number": "XXXXX", "issue_name": "ALL", "component": "ALL"}
        
        Args:
            serial_number: The equipment serial number (e.g., "290T434", "337X380")
            
        Returns:
            list[dict]: A deduplicated list of dictionaries, each containing:
                - serial_number: The provided serial number
                - issue_id: A unique UUID assigned per entry
                - component: A component from the heatmap
                - issue_name: An issue name from the heatmap
                - issue_grouping: The issue grouping category from the heatmap
                - issue_question: The issue prompt text from the heatmap
                - severity_criteria: A dict of severity levels (not_mentioned, light, medium, heavy, immediate)

        Side Effects:
            Saves the resulting matrix as an Excel file at <RUN_ARTIFACTS_DIR>/<esn>/heatmap.xlsx.
        """
       
        # Build the expanded list by pairing the serial number with each heatmap entry
        heatmap_reference = []
        for row in self.all_issues:
            # Extract component and issue_name from each heatmap row
            row_comp = str(row.get("component", "")).strip()
            row_issue = str(row.get("issue_name", "")).strip()
            
            # Create a run entry with heatmap data.
            # serial_number is stored on every entry so that retrieve_evidence_from_databricks
            # can reconstruct the ESN from the matrix without needing it passed as an argument.
            # issue_id is a unique UUID assigned per issue_name, used to key FSR results.
            heatmap_reference.append({
                "serial_number": serial_number,
                "issue_id": str(uuid.uuid4()),
                "component": row_comp,
                "issue_name": row_issue,
                "issue_grouping": row.get("issue_grouping"),
                "issue_question": row.get("issue_prompt"),
                "severity_criteria": {
                    "not_mentioned": row.get("severity_criteria_0"),
                    "light": row.get("severity_criteria_1"),
                    "medium": row.get("severity_criteria_2"),
                    "heavy": row.get("severity_criteria_3"),
                    "immediate": row.get("severity_criteria_4"),
                },
            })
        
        # Deduplicate entries based on (issue_name, component) tuple
        # This ensures no duplicate combinations in case the heatmap has redundant rows
        unique_combo_set = set()
        esn_issue_list = []
        for e in heatmap_reference:
            # Create a unique key (case-insensitive for issue_name and component)
            key = (e["issue_name"].lower(), e["component"].lower())
            if key not in unique_combo_set:
                unique_combo_set.add(key)
                esn_issue_list.append(e)

        # Save the heatmap to an Excel file for inspection.
        # Path: <RUN_ARTIFACTS_DIR>/<esn>/heatmap.xlsx (default: /tmp/run/<esn>/heatmap.xlsx)
        # The severity_criteria column contains dicts and will be serialised as strings in Excel.
        try:
            run_dir = Path(os.getenv("RUN_ARTIFACTS_DIR", "/tmp/run")) / serial_number
            run_dir.mkdir(parents=True, exist_ok=True)
            heatmap_path = run_dir / "heatmap.xlsx"
            pd.DataFrame(esn_issue_list).to_excel(heatmap_path, index=False, engine="openpyxl")
            logger.info("Heatmap saved to %s", heatmap_path)
        except Exception as e:
            # Non-fatal: log and continue — saving the file must not block the main flow
            logger.warning("Failed to save heatmap to Excel: %s", e)

        return esn_issue_list

    async def retrieve_heatmap_issues_from_databricks(
        self,
        esn: str,
        persona: str,
        component_type: str | None = None
    ) -> str | dict[str, Any]:
        """
        Fetch heatmap issues from Databricks and build the ESN-issue matrix.

        Populates self.esn_issue_matrix with all issue/component combinations
        for the given ESN. Uses a cached heatmap.xlsx if available on disk;
        otherwise calls the MCP heatmap tool.

        Args:
            esn: The equipment serial number
            persona: Persona filter (e.g., "RE", "OE")
            component_type: Component type filter (e.g., "Stator", "Rotor")

        Returns:
            True on success, False on error.

        Workflow:
            1. Check for cached heatmap.xlsx on disk; if found, reload matrix from it
            2. Otherwise, call MCP heatmap tool (load_heatmap_api_v1_heatmap_load_get)
            3. Build ESN-issue matrix via _form_esn_issue_matrix
        """
        # Step 1: Check if heatmap.xlsx already exists in the run outputs folder for this ESN.
        # If the file is present, we can skip the expensive MCP heatmap tool call and
        # rebuild self.esn_issue_matrix directly from the persisted Excel file.
        run_dir = Path(os.getenv("RUN_ARTIFACTS_DIR", "/tmp/run")) / esn
        heatmap_path = run_dir / "heatmap.xlsx"
        if heatmap_path.exists():
            logger.info(f"heatmap.xlsx already exists at {heatmap_path}, skipping MCP heatmap tool call")
            try:
                # Read the previously saved heatmap Excel back into a DataFrame
                df = pd.read_excel(heatmap_path, engine="openpyxl")

                # Reconstruct self.esn_issue_matrix from the DataFrame rows.
                # severity_criteria was serialised as a string repr of a dict in Excel;
                # parse it back to a Python dict using ast.literal_eval.
                self.esn_issue_matrix = []
                for _, row in df.iterrows():
                    entry = row.to_dict()
                    raw_sc = entry.get("severity_criteria", "")
                    if isinstance(raw_sc, str) and raw_sc not in ("nan", ""):
                        try:
                            entry["severity_criteria"] = ast.literal_eval(raw_sc)
                        except (ValueError, SyntaxError):
                            # If parsing fails, default to an empty dict
                            entry["severity_criteria"] = {}
                    self.esn_issue_matrix.append(entry)

                logger.info(f"Loaded ESN-issue matrix from existing heatmap ({len(self.esn_issue_matrix)} entries)")
                if self.esn_issue_matrix:
                    return True
                logger.warning(
                    "Cached heatmap file is empty for ESN=%s; refreshing from MCP heatmap tool",
                    esn,
                )
            except Exception as e:
                # If reloading fails for any reason, fall through to the MCP tool call
                logger.warning(f"Failed to reload heatmap from {heatmap_path}, proceeding with MCP call: {e}")
        else:
        # Step 2: Call heatmap tool to load all issue/component combinations
            heatmap_persona = _normalize_heatmap_persona(persona)
            logger.info("Calling MCP tool 'read_risk_matrix' for persona=%s (from %s)",
            heatmap_persona,
            persona,
        )
            try:
                heatmap_tool_args: dict[str, Any] = {
                    "equipment_type": "GEN",
                    "persona": heatmap_persona,
                    "component": "",
                }
                heatmap_result = await run_http_with_tool("read_risk_matrix", heatmap_tool_args)
                logger.info("Heatmap result received")
                self.all_issues = heatmap_result.get("data", []) if isinstance(heatmap_result, dict) else []
                logger.debug(f"All issues: {self.all_issues}")  # Log all issues
                logger.debug(f"Heat Map result {heatmap_result}")
            except Exception as e:
                logger.error(f"Failed to fetch heatmap data: {e}")
                return False

        # Step 3: Build the ESN-issue matrix using the extracted ESN
        try:
            self.esn_issue_matrix = self._form_esn_issue_matrix(esn)
            logger.info(f"Formed ESN-issue matrix with {len(self.esn_issue_matrix)} entries for ESN={esn}")
            logger.debug(f"ESN-issue matrix: {self.esn_issue_matrix}")
            if not self.esn_issue_matrix:
                logger.error("No issue rows available to analyze for ESN=%s", esn)
                return False

            return True
        except Exception as e:
            logger.error(f"Failed to build ESN-issue matrix for ESN={esn}: {e}")
            return False

    async def retrieve_ibat_from_databricks(self) -> bool:
        """
        Fetch IBAT equipment metadata via a direct REST call to data-service.

        Calls GET /api/v1/ibat/ibat/equipment with the ESN derived from
        self.esn_issue_matrix. Uses a cached ibat_result.json if available
        on disk; otherwise makes the REST call and persists the result.

        Populates self.ibat_data with the first row of the IBAT response.

        Prerequisite: self.esn_issue_matrix must be populated by
        retrieve_heatmap_issues_from_databricks.

        Returns:
            True on success, False on error.
        """
        if not getattr(self, "esn_issue_matrix", None):
            logger.error(
                "esn_issue_matrix is empty or not set. "
                "Call retrieve_heatmap_issues_from_databricks first."
            )
            return False

        esn = self.esn_issue_matrix[0].get("serial_number")

        # Check if IBAT result already cached on disk
        run_dir = Path(os.getenv("RUN_ARTIFACTS_DIR", "/tmp/run")) / esn
        ibat_path = run_dir / "ibat_result.json"
        if ibat_path.exists():
            logger.info(f"ibat_result.json already exists at {ibat_path}, loading from disk")
            try:
                with ibat_path.open(encoding="utf-8") as fh:
                    rows = json.load(fh)
                if isinstance(rows, list) and len(rows) > 0:
                    self.ibat_data = rows[0]
                    logger.info("Loaded IBAT data from disk (%d rows)", len(rows))
                    return True
                logger.info("Cached ibat_result.json is empty, will re-fetch")
            except Exception as e:
                logger.warning(f"Failed to reload IBAT from {ibat_path}, proceeding with REST call: {e}")
        else:
            # Call IBAT direct endpoint via REST (same as assessment metadata fetch)
            logger.info(f"Calling data-service GET /dataservices/api/v1/ibat/equipment for ESN={esn}")
            start_time = datetime.now()
            try:
                ibat_result = await call_rest_api(
                    f"/dataservices/api/v1/ibat/equipment?equip_serial_number={esn}"
                )
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.info(f"IBAT REST call completed in {elapsed:.2f} seconds")
                logger.info(f"IBAT raw result type={type(ibat_result).__name__}, value={ibat_result}")

                # Extract rows from response
                rows = ibat_result.get("data", []) if isinstance(ibat_result, dict) else []
                logger.info(f"IBAT returned {len(rows)} rows for ESN={esn}")

                self.ibat_data = rows[0] if rows else {}
                self._save_run_artifact(esn, "ibat_result.json", rows)
                return True
            except Exception as e:
                logger.error(f"Failed to fetch IBAT data for ESN={esn}: {e}")
                self.ibat_data = {}
                return False

    async def retrieve_evidence_from_databricks(self, datasources: list[str] | None = None) -> str | dict[str, Any]:
        """
        Call FSR and ER MCP tools in parallel to gather evidence for all issues.

        Uses self.esn_issue_matrix — populated by
        retrieve_heatmap_issues_from_databricks — to build the issue_prompts
        list sent to both tools. Each matrix entry contributes:
          - issue_id        → unique identifier in the issue_prompts payload
          - issue_question   → issue_prompt argument for FSR and ER tools
          - serial_number   → esn argument for FSR and ER tools

        Args:
            datasources: List of datasource labels to retrieve (e.g., ["FSR", "ER"]).
                         If None or empty, defaults to calling both FSR and ER.

        Returns:
            True on success, or False if the matrix is empty / a tool call fails.

        Workflow:
            1. Validate that self.esn_issue_matrix has been populated
            2. Build issue_prompts list from all matrix entries
            3. Call FSR and/or ER tools based on datasources parameter
            4. If datasurces contains both then Call FSR and ER tools in parallel via asyncio.gather
            5. Persist FSR and ER results as run artifacts to disk
            6. Generate user prompts for each issue and save to disk
        """
        # Step 1: Guard — matrix must be populated before calling this method
        if not getattr(self, "esn_issue_matrix", None):
            logger.error(
                "esn_issue_matrix is empty or not set. "
                "Call retrieve_heatmap_issues_from_databricks first."
            )
            return False

        # ESN is the same across all matrix entries; read it from the first item
        first_item = self.esn_issue_matrix[0]
        esn = first_item.get("serial_number")

        # send the full matrix once end-to-end flow is validated.
        issue_prompts_list = [
            {"issue_id": item["issue_id"], "issue_prompt": item["issue_question"]}
            for item in self.esn_issue_matrix
        ]

        # Determine which datasources to call — default to both if not specified
        if not datasources:
            datasources = ["FSR", "ER"]
        
        # Normalize datasource names to uppercase for consistent matching
        datasources_upper = [ds.upper() for ds in datasources]
        
        call_fsr = "FSR" in datasources_upper
        call_er = "ER" in datasources_upper
        
        logger.info(
            f"Datasources requested: {datasources_upper} | "
            f"call_fsr={call_fsr}, call_er={call_er}"
        )
        logger.info(
            f"Sending {len(issue_prompts_list)} issue prompts for esn='{esn}'"
        )

        # Start counting time for parallel FSR + ER retrieval
        start_time = datetime.now()

        fsr_result = None
        tool_results_er = None

        try:
            # Case 1: Both FSR and ER — call in parallel
            if call_fsr and call_er:
                logger.info(
                    f"Calling FSR and ER tools in parallel "
                    f"with {len(issue_prompts_list)} issue_prompts, esn='{esn}'"
                )
                fsr_result, tool_results_er = await asyncio.gather(
                    run_http_with_tool("query_fsr", {
                        "issue_prompts": issue_prompts_list,
                        "esn": esn,
                    }),
                    run_http_with_tool("query_er", {
                        "issue_prompts": issue_prompts_list,
                        "esn": esn,
                    }),
                )
                logger.info("FSR and ER results received")
            
            # Case 2: Only FSR
            elif call_fsr:
                logger.info(
                    f"Calling FSR tool only "
                    f"with {len(issue_prompts_list)} issue_prompts, esn='{esn}'"
                )
                fsr_result = await run_http_with_tool(
                    "query_fsr", {
                        "issue_prompts": issue_prompts_list,
                        "esn": esn,
                    }
                )
                logger.info("FSR result received")
            
            # Case 3: Only ER
            elif call_er:
                logger.info(
                    f"Calling ER tool only "
                    f"with {len(issue_prompts_list)} issue_prompts, esn='{esn}'"
                )
                tool_results_er = await run_http_with_tool(
                    "query_er", {
                        "issue_prompts": issue_prompts_list,
                        "esn": esn,
                    }
                )
                logger.info("ER result received")
            
            # Case 4: Neither FSR nor ER requested
            else:
                logger.warning(
                    f"No recognized datasources in {datasources_upper}. "
                    "Skipping FSR and ER tool calls."
                )
        except Exception as e:
            logger.error(f"Failed to retrieve evidence from Databricks: {e}")
            return False

        # Persist responses for debugging / offline analysis (only if retrieved)
        if fsr_result is not None:
            self._save_run_artifact(esn, "fsr_result.json", fsr_result)
        if tool_results_er is not None:
            self._save_run_artifact(esn, "er_result.json", tool_results_er)

        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"FSR + ER parallel retrieval completed in {elapsed_time} seconds")
        
        # Generate user prompt for LLM
        for item in self.esn_issue_matrix:
            generate_user_prompt_for_LLM(issue_id=item["issue_id"])

        return True