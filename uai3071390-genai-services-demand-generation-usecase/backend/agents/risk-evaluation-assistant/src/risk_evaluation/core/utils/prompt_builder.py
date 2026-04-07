"""Standalone prompt builder module for REChain user prompt generation.

This module replicates the build_user_prompt() functionality from prompting.py
and includes all supporting methods and dummy test data for testing purposes.

The module formats HEATMAP, IBAT, FSR chunks, and ER chunks into a structured
LLM user prompt following the exact format used in the REChain pipeline.

Uses LangChain PromptTemplate loaded from YAML file for structured prompt generation.
"""

from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import yaml
from langchain_core.prompts import PromptTemplate

#Initialize logger
from risk_evaluation.core.config.logger_config import get_logger

logger = get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────

# Regex pattern to replace "nan" values in the output
_NAN_RE = re.compile(r":\s*nan\b", flags=re.IGNORECASE)

# IBAT fields mapping: (field_name, display_label)
_IBAT_FIELDS = [
    ("equip_serial_number", "Serial Number"),
    ("equipment_name", "Plant"),
    ("equipment_model", "Equipment Model"),
    ("equipment_code", "Equipment Code"),
    ("cooling_system", "Cooling System"),
    ("excitation_system", "Excitation System"),
    ("equipment_status", "Status"),
    ("present_apparent_pwr_mva", "Capacity MVA"),
    ("present_voltage_v", "Voltage"),
    ("speed_rpm", "Speed RPM"),
    ("equipment_comm_date", "Commission Date"),
    ("contract_type", "Contract Type"),
    ("csa_contract_number", "CSA Contract"),
    ("er_support_level", "ER Support Level"),
    ("rotor_rewind", "Rotor Rewind"),
    ("stator_rewind", "Stator Rewind"),
]

# Severity criteria field mapping
_SEVERITY_LABELS = {
    "severity_criteria_0": "Not Mentioned",
    "severity_criteria_1": "Light",
    "severity_criteria_2": "Medium",
    "severity_criteria_3": "Heavy",
    "severity_criteria_4": "Immediate",
}


# ── Prompt Template Loading (from YAML) ──────────────────────────

def _load_prompt_template(prompt_filename: str) -> PromptTemplate:
        """Load prompt template from YAML file in prompt_lib folder."""
        # Navigate from core/utils/ up 3 levels to reach risk_evaluation/,
        # where the prompt_lib/ directory lives.
        prompt_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'prompt_lib',
            prompt_filename
        )

        try:
            with open(prompt_file, encoding='utf-8') as f:
                prompt_config = yaml.safe_load(f)

            logger.info(f"Loaded prompt template from {prompt_file}")
            return PromptTemplate(
                input_variables=prompt_config['prompt_template']['input_variables'],
                template=prompt_config['prompt_template']['template']
            )
        except Exception as e:
            logger.error(f"Error loading prompt template from {prompt_file}: {e}")
            raise e

# Placeholder kept for legacy compatibility; template is loaded on demand in build_user_prompt
llm_prompt_template = None


def _find_run_dir(issue_id: str) -> Path:
    """
    Scan run/ subdirectories to find the ESN folder whose heatmap.xlsx contains issue_id.

    The run/ directory is resolved relative to this module's package root
    (risk_evaluation/run/), matching the path used in _form_esn_issue_matrix.

    Args:
        issue_id: UUID string identifying the issue to look up

    Returns:
        Path: The ESN subdirectory that contains a heatmap.xlsx with the given issue_id

    Raises:
        FileNotFoundError: If run/ does not exist or no matching directory is found
    """
    # RUN_ARTIFACTS_DIR must match what risk_assessment_creation.py uses when writing artifacts.
    # In Docker, this is set via compose.yml (e.g. /app/run_outputs); locally defaults to /tmp/run.
    base_run = Path(os.getenv("RUN_ARTIFACTS_DIR", "/tmp/run"))
    if not base_run.is_dir():
        raise FileNotFoundError(f"Run directory not found: {base_run}")

    for esn_dir in base_run.iterdir():
        if not esn_dir.is_dir():
            continue
        heatmap_path = esn_dir / "heatmap.xlsx"
        if not heatmap_path.exists():
            continue
        try:
            df = pd.read_excel(heatmap_path, engine="openpyxl")
            if issue_id in df["issue_id"].astype(str).values:
                logger.info("Found issue_id='%s' in ESN folder '%s'", issue_id, esn_dir.name)
                return esn_dir
        except Exception as e:
            logger.warning("Could not read heatmap at %s: %s", heatmap_path, e)
            continue

    raise FileNotFoundError(
        f"No run/<esn>/heatmap.xlsx found containing issue_id='{issue_id}'"
    )


# ── Data Classes ─────────────────────────────────────────────────

@dataclass(slots=True)
class PromptBuildResult:
    """Result object containing the built prompt and metadata."""
    user_prompt: str
    fsr_chunk_count: int
    er_chunk_count: int


# ── Helper Functions ─────────────────────────────────────────────

def clean_scalar(value: Any) -> str:
    """
    Clean and normalize scalar values to strings.
    
    Handles None values, pandas NaN values, and converts all other types
    to stripped strings.
    
    Args:
        value: Any scalar value to clean
        
    Returns:
        str: Cleaned string representation, empty string if None/NaN
    """
    if value is None:
        return ""
    
    # Handle pandas NaN values if pandas is available
    try:
        import pandas as pd
        if pd.isna(value):
            return ""
    except (ImportError, Exception):
        # pandas not available or error checking - continue
        pass
    
    # Convert to string and strip whitespace
    return str(value).strip() if isinstance(value, str) else str(value).strip()


def _truncate(value: Any, max_chars: int) -> str:
    """
    Truncate text to maximum character length.
    
    Args:
        value: Value to truncate
        max_chars: Maximum number of characters allowed
        
    Returns:
        str: Truncated text with " ... [truncated]" suffix if truncated,
             or "N/A" if value is empty
    """
    text = clean_scalar(value)
    if not text:
        return "N/A"
    
    # Return as-is if within limit
    if len(text) <= max_chars:
        return text
    
    # Truncate and add marker
    return text[:max_chars].rstrip() + " ... [truncated]"


def _dedupe_chunks(chunks: List[Dict], key_fields: tuple[str, ...]) -> List[Dict]:
    """
    Remove duplicate chunks based on specified key fields.
    
    Uses a set to track unique combinations of key field values.
    Preserves the order of first occurrence.
    
    Args:
        chunks: List of chunk dictionaries
        key_fields: Tuple of field names to use as deduplication key
        
    Returns:
        List[Dict]: Deduplicated list of chunks
    """
    seen: set[tuple[str, ...]] = set()
    unique: List[Dict] = []
    
    for chunk in chunks:
        # Build key from specified fields
        key = tuple(clean_scalar(chunk.get(field, "")) for field in key_fields)
        
        # Add chunk if key not seen before
        if key not in seen:
            seen.add(key)
            unique.append(chunk)
    
    return unique


def _select_chunks(chunks: List[Dict], max_items: int, key_fields: tuple[str, ...]) -> List[Dict]:
    """
    Select and deduplicate chunks up to maximum count.
    
    First deduplicates chunks, then takes the first max_items entries.
    
    Args:
        chunks: List of chunk dictionaries
        max_items: Maximum number of chunks to return
        key_fields: Tuple of field names for deduplication
        
    Returns:
        List[Dict]: Selected and deduplicated chunks
    """
    return _dedupe_chunks(chunks, key_fields)[:max_items]


# ── Section Formatters ───────────────────────────────────────────

def format_ibat_section(ibat: Dict) -> str:
    """
    Format IBAT equipment metadata section.
    
    Converts IBAT dictionary into a formatted text section with labeled fields.
    Uses the _IBAT_FIELDS mapping to extract and label each field.
    
    Args:
        ibat: Dictionary containing IBAT equipment data
        
    Returns:
        str: Formatted IBAT section text
    """
    if not ibat:
        return "IBAT DATA:\nNo IBAT data available."
    
    lines = ["IBAT DATA:"]
    
    # Iterate through defined IBAT fields and format each
    for field_name, label in _IBAT_FIELDS:
        value = clean_scalar(ibat.get(field_name, "")) or "N/A"
        lines.append(f"{label}: {value}")
    
    return "\n".join(lines)


def format_heatmap_section(heatmap: Dict) -> str:
    """
    Format heatmap question and severity criteria section.
    
    Extracts component, issue name, grouping, prompt, and all severity criteria
    from the heatmap data and formats them into a structured text section.
    
    Args:
        heatmap: Dictionary containing heatmap issue data
        
    Returns:
        str: Formatted heatmap section text
    """
    if not heatmap:
        return "HEATMAP QUESTION:\nNo heatmap data available."
    
    lines = [
        "HEATMAP QUESTION:",
        f"Component: {clean_scalar(heatmap.get('component', '')) or 'N/A'}",
        f"Issue Name: {clean_scalar(heatmap.get('issue_name', '')) or 'N/A'}",
        f"Issue Grouping: {clean_scalar(heatmap.get('issue_grouping', '')) or 'N/A'}",
        f"Issue Question: {clean_scalar(heatmap.get('issue_prompt', '')) or 'N/A'}",
        "Severity Criteria:",
    ]
    
    # Add severity criteria if present
    for col, label in _SEVERITY_LABELS.items():
        val = clean_scalar(heatmap.get(col, ""))
        if val:
            lines.append(f"  {label}: {val}")
    
    return "\n".join(lines)


def format_fsr_section(chunks: List[Dict], max_chunk_chars: int = 10000) -> str:
    """
    Format Field Service Report (FSR) chunks section.
    
    Each chunk includes metadata (chunk_id, pdf_name, page_number, serial, score)
    and the chunk text content truncated to max_chunk_chars.
    
    Args:
        chunks: List of FSR chunk dictionaries
        max_chunk_chars: Maximum characters per chunk text (default: 10000)
        
    Returns:
        str: Formatted FSR chunks section text
    """
    if not chunks:
        return "No FSR chunks available."
    
    parts: List[str] = []
    
    for i, chunk in enumerate(chunks, 1):
        # Extract and format each chunk with metadata
        part = (
            f"--- FSR Chunk {i} ---\n"
            f"Chunk ID: {clean_scalar(chunk.get('chunk_id', '')) or 'N/A'}\n"
            f"Report Name: {clean_scalar(chunk.get('pdf_name', '')) or 'N/A'}\n"
            f"Page Number: {clean_scalar(chunk.get('page_number', '')) or 'N/A'}\n"
            f"Serial: {clean_scalar(chunk.get('generator_serial', '')) or 'N/A'}\n"
            f"Score: {clean_scalar(chunk.get('score', '')) or 'N/A'}\n"
            f"Context: {_truncate(chunk.get('chunk_text', ''), max_chunk_chars)}"
        )
        parts.append(part)
    
    return "\n\n".join(parts)


def format_er_section(chunks: List[Dict], max_chunk_chars: int = 10000) -> str:
    """
    Format Engineering Record (ER) chunks section.
    
    Each chunk includes metadata (er_number, opened_at, component, status,
    field_action_taken, score) and the chunk text content truncated to
    max_chunk_chars.
    
    Args:
        chunks: List of ER chunk dictionaries
        max_chunk_chars: Maximum characters per chunk text (default: 10000)
        
    Returns:
        str: Formatted ER chunks section text
    """
    if not chunks:
        return "No ER chunks available."
    
    parts: List[str] = []
    
    for i, chunk in enumerate(chunks, 1):
        # Extract and format each chunk with metadata
        # Try both 'chunk_text' and 'Text' fields for content
        chunk_content = chunk.get('chunk_text', chunk.get('Text', ''))
        
        part = (
            f"--- ER Chunk {i} ---\n"
            f"ER Number: {clean_scalar(chunk.get('er_number', '')) or 'N/A'}\n"
            f"Opened At: {clean_scalar(chunk.get('opened_at', '')) or 'N/A'}\n"
            f"Component: {clean_scalar(chunk.get('u_component', '')) or 'N/A'}\n"
            f"Status: {clean_scalar(chunk.get('status', '')) or 'N/A'}\n"
            f"Field Action Taken: {clean_scalar(chunk.get('u_field_action_taken', '')) or 'N/A'}\n"
            f"Score: {clean_scalar(chunk.get('score', '')) or 'N/A'}\n"
            f"Context: {_truncate(chunk_content, max_chunk_chars)}"
        )
        parts.append(part)
    
    return "\n\n".join(parts)


# ── Main Prompt Builder ──────────────────────────────────────────

def build_user_prompt(
    ibat: Dict,
    heatmap: Dict,
    fsr_chunks: List[Dict],
    er_chunks: List[Dict],
    max_fsr_chunks: int = 20,
    max_er_chunks: int = 20,
    max_chunk_chars: int = 10000,
) -> PromptBuildResult:
    """
    Assemble the complete user prompt from all 4 data sources using LangChain PromptTemplate.
    
    This is the main entry point for building the LLM user prompt.
    It combines HEATMAP question/criteria, IBAT equipment data,
    FSR field service report chunks, and ER engineering record chunks
    into a single formatted prompt string using a YAML-based template.
    
    The function:
    1. Deduplicates and selects chunks based on max limits
    2. Formats each data source section using dedicated formatters
    3. Uses LangChain PromptTemplate to combine sections with YAML structure
    4. Cleans up any "nan" text artifacts in the final output
    
    Args:
        ibat: IBAT equipment metadata dictionary
        heatmap: Heatmap issue and severity criteria dictionary
        fsr_chunks: List of FSR chunk dictionaries
        er_chunks: List of ER chunk dictionaries
        max_fsr_chunks: Maximum number of FSR chunks to include (default: 20)
        max_er_chunks: Maximum number of ER chunks to include (default: 20)
        max_chunk_chars: Maximum characters per chunk text (default: 10000)
        
    Returns:
        PromptBuildResult: Object containing the formatted prompt and metadata
    """
    try:
        # Step 1: Select and deduplicate FSR chunks
        # FSR chunks are deduplicated by (chunk_id, pdf_name, page_number)
        selected_fsr = _select_chunks(
            fsr_chunks, 
            max_fsr_chunks, 
            ("chunk_id", "pdf_name", "page_number")
        )
        
        # Step 2: Select and deduplicate ER chunks
        # ER chunks are deduplicated by (er_number, chunk_index, opened_at)
        selected_er = _select_chunks(
            er_chunks, 
            max_er_chunks, 
            ("er_number", "chunk_index", "opened_at")
        )
        
        # Step 3: Format each section
        heatmap_text = format_heatmap_section(heatmap)
        logger.debug(f"Formatted heatmap section:\n{heatmap_text}")
        ibat_text = format_ibat_section(ibat)
        fsr_text = format_fsr_section(selected_fsr, max_chunk_chars)
        er_text = format_er_section(selected_er, max_chunk_chars)
        
        # Step 4: Build prompt string using LangChain PromptTemplate.
        # format() injects the formatted sections into the template placeholders.
        prompt_template = _load_prompt_template("risk_analysis_user_prompt_gen.yaml")
        prompt = prompt_template.format(
            heatmap_section=heatmap_text,
            ibat_section=ibat_text,
            fsr_section=fsr_text,
            er_section=er_text,
        )

        # Step 5: Clean up any "nan" artifacts (replace ": nan" with ": N/A")
        prompt = _NAN_RE.sub(": N/A", prompt)
        
        # Step 6: Return result with metadata
        return PromptBuildResult(
            user_prompt=prompt,
            fsr_chunk_count=len(selected_fsr),
            er_chunk_count=len(selected_er),
        )
        
    except Exception as e:
        # Handle any errors gracefully
        error_msg = f"Error building user prompt: {str(e)}"
        print(f"[ERROR] {error_msg}")
        
        # Return minimal prompt with error indication
        return PromptBuildResult(
            user_prompt=f"ERROR: {error_msg}\n\nPartial data may be incomplete.",
            fsr_chunk_count=0,
            er_chunk_count=0,
        )

def collect_heatmap_data(issue_id: str, run_dir: Path) -> Dict:
    """
    Load heatmap data for a given issue_id from the heatmap.xlsx saved under run/<esn>/.

    Reads the row matching issue_id, renames issue_question → issue_prompt, and
    flattens the nested severity_criteria dict into the flat keys expected by
    format_heatmap_section.

    Args:
        issue_id: UUID string identifying the issue
        run_dir:  Path to the run/<esn>/ directory

    Returns:
        Dict: Heatmap dictionary compatible with format_heatmap_section
    """
    heatmap_path = run_dir / "heatmap.xlsx"
    df = pd.read_excel(heatmap_path, engine="openpyxl")

    # Locate the row for this issue_id
    mask = df["issue_id"].astype(str) == issue_id
    if not mask.any():
        raise ValueError(f"issue_id='{issue_id}' not found in {heatmap_path}")
    row = df[mask].iloc[0].to_dict()

    # Parse severity_criteria — pandas saves dicts as their str() representation.
    # ast.literal_eval converts it back to a Python dict safely.
    severity_criteria: Dict = {}
    raw_sc = row.get("severity_criteria", "")
    if raw_sc and isinstance(raw_sc, str) and raw_sc not in ("nan", ""):
        try:
            severity_criteria = ast.literal_eval(raw_sc)
        except (ValueError, SyntaxError) as e:
            logger.warning(
                "Could not parse severity_criteria for issue_id='%s': %s", issue_id, e
            )

    # severity_criteria keys in the matrix → flat keys expected by format_heatmap_section
    _sc_key_map = {
        "not_mentioned": "severity_criteria_0",
        "light":         "severity_criteria_1",
        "medium":        "severity_criteria_2",
        "heavy":         "severity_criteria_3",
        "immediate":     "severity_criteria_4",
    }

    heatmap: Dict = {
        "component":     clean_scalar(row.get("component", "")),
        "issue_name":    clean_scalar(row.get("issue_name", "")),
        "issue_grouping": clean_scalar(row.get("issue_grouping", "")),
        # issue_question in the matrix is the same field as issue_prompt in the formatter
        "issue_prompt":  clean_scalar(row.get("issue_question", "")),
    }
    # Flatten severity_criteria into the expected flat keys
    for sc_key, flat_key in _sc_key_map.items():
        heatmap[flat_key] = clean_scalar(severity_criteria.get(sc_key, ""))

    return heatmap


def collect_ibat_data(run_dir: Path) -> Dict:
    """
    Load IBAT equipment metadata from ibat_result.json saved under run/<esn>/.

    Falls back to an empty dict if the file is missing or unreadable.

    Args:
        run_dir: Path to the run/<esn>/ directory

    Returns:
        Dict: First IBAT row, or empty dict if unavailable
    """
    ibat_path = run_dir / "ibat_result.json"
    if not ibat_path.exists():
        logger.warning("ibat_result.json not found at %s, returning empty IBAT data", ibat_path)
        return {}
    try:
        with ibat_path.open(encoding="utf-8") as fh:
            rows = json.load(fh)
        if isinstance(rows, list) and rows:
            return rows[0]
        if isinstance(rows, dict):
            return rows
        return {}
    except Exception as e:
        logger.warning("Failed to load ibat_result.json from %s: %s", ibat_path, e)
        return {}


def collect_fsr_chunks(issue_id: str, run_dir: Path) -> List[Dict]:
    """
    Load FSR chunks for a given issue_id from fsr_result.json saved under run/<esn>/.

    The FSR result file has the format:
        {"data": {"<issue_id>": [{"#", "chunk_id", "Document Name", "Page Number",
                                   "Evidence", "ESN"}, ...]}}

    Keys are remapped to those expected by format_fsr_section:
        chunk_id        → chunk_id
        Document Name   → pdf_name
        Page Number     → page_number
        Evidence        → chunk_text
        ESN             → generator_serial

    Args:
        issue_id: UUID string identifying the issue
        run_dir:  Path to the run/<esn>/ directory

    Returns:
        List[Dict]: FSR chunk dictionaries compatible with format_fsr_section
    """
    fsr_path = run_dir / "fsr_result.json"
    with fsr_path.open(encoding="utf-8") as fh:
        raw = json.load(fh)

    # Guard: tool may have returned no content (saved as JSON null)
    if not isinstance(raw, dict):
        logger.warning("fsr_result.json for issue_id='%s' is not a dict (got %s), returning empty", issue_id, type(raw).__name__)
        return []

    # Navigate to the list for this specific issue_id
    chunks_raw: List[Dict] = raw.get("data", {}).get(issue_id, [])

    # Remap keys to the format expected by format_fsr_section
    return [
        {
            "chunk_id":        item.get("chunk_id", ""),
            "pdf_name":        item.get("Document Name", ""),
            "page_number":     item.get("Page Number", ""),
            "chunk_text":      item.get("Evidence", ""),
            "generator_serial": item.get("ESN", ""),
            # score is not stored in the FSR result; format_fsr_section will show N/A
        }
        for item in chunks_raw
    ]


def collect_er_chunks(issue_id: str, run_dir: Path) -> List[Dict]:
    """
    Load ER chunks for a given issue_id from er_result.json saved under run/<esn>/.

    The ER result file has the format:
        {"data": {"<issue_id>": [{"chunk_id", "er_case_number", "chunk_text",
                                   "serial_number", "opened_at", "status",
                                   "u_component", "u_field_action_taken",
                                   "equipment_id"}, ...]}}

    Keys are remapped to those expected by format_er_section:
        er_case_number      → er_number
        chunk_text          → chunk_text  (unchanged)
        opened_at           → opened_at   (unchanged)
        status              → status      (unchanged)
        u_component         → u_component (unchanged)
        u_field_action_taken → u_field_action_taken (unchanged)

    Args:
        issue_id: UUID string identifying the issue
        run_dir:  Path to the run/<esn>/ directory

    Returns:
        List[Dict]: ER chunk dictionaries compatible with format_er_section
    """
    er_path = run_dir / "er_result.json"
    with er_path.open(encoding="utf-8") as fh:
        raw = json.load(fh)

    # Guard: tool may have returned no content (saved as JSON null)
    if not isinstance(raw, dict):
        logger.warning("er_result.json for issue_id='%s' is not a dict (got %s), returning empty", issue_id, type(raw).__name__)
        return []

    # Navigate to the list for this specific issue_id
    chunks_raw: List[Dict] = raw.get("data", {}).get(issue_id, [])

    # Remap keys to the format expected by format_er_section
    return [
        {
            # er_case_number in the ER result maps to er_number expected by the formatter
            "er_number":            item.get("er_case_number", ""),
            "chunk_text":           item.get("chunk_text", ""),
            "opened_at":            item.get("opened_at", ""),
            "status":               item.get("status", ""),
            "u_component":          item.get("u_component", ""),
            "u_field_action_taken": item.get("u_field_action_taken", ""),
            # score is not stored in the ER result; format_er_section will show N/A
        }
        for item in chunks_raw
    ]

def generate_user_prompt_for_LLM(issue_id: str) -> None:
    """
    Build the LLM user prompt for a given issue_id and save it to disk.

    Workflow:
        1. Locate the run/<esn>/ directory containing this issue_id
        2. Load heatmap data from heatmap.xlsx (issue row)
        3. Load FSR chunks from fsr_result.json (keyed by issue_id)
        4. Load ER chunks from er_result.json (keyed by issue_id)
        5. Assemble the full prompt via build_user_prompt
        6. Save the prompt to run/<esn>/user_prompt_<issue_id>.txt

    Args:
        issue_id: UUID string identifying the issue to generate a prompt for
    """
    # Step 1: Find the ESN folder that owns this issue_id
    run_dir = _find_run_dir(issue_id)

    # Step 2-4: Load each data source from disk
    heatmap_data = collect_heatmap_data(issue_id, run_dir)
    ibat_data = collect_ibat_data(run_dir)
    fsr_chunks_data = collect_fsr_chunks(issue_id, run_dir)
    er_chunks_data = collect_er_chunks(issue_id, run_dir)

    # Step 5: Build the prompt
    result = build_user_prompt(
        ibat=ibat_data,
        heatmap=heatmap_data,
        fsr_chunks=fsr_chunks_data,
        er_chunks=er_chunks_data,
        max_fsr_chunks=20,
        max_er_chunks=20,
        max_chunk_chars=10000,
    )

    # Step 6: Save the final user prompt to disk
    output_path = run_dir / f"user_prompt_{issue_id}.txt"
    try:
        with output_path.open("w", encoding="utf-8") as fh:
            fh.write(result.user_prompt)
        logger.info(
            "User prompt saved to %s (fsr_chunks=%d, er_chunks=%d)",
            output_path, result.fsr_chunk_count, result.er_chunk_count,
        )
    except Exception as e:
        logger.warning("Failed to save user prompt to %s: %s", output_path, e)
