# Create server parameters for stdio connection
import json
from typing import Any

import httpx
import traceback

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

#Loading environment variables from config
from risk_evaluation import config

# Initialize logger
from risk_evaluation.core.config.logger_config import get_logger

logger = get_logger(__name__)

# Extended timeout for slow Databricks queries (300s read, 30s connect)
MCP_HTTP_TIMEOUT = httpx.Timeout(300.0, connect=30.0)


async def run_http_with_tool(tool_name: str, tool_args: dict[str, Any]) -> Any:
    """
    Execute an MCP tool call via HTTP transport.
    
    Args:
        tool_name: Name of the MCP tool to call
        tool_args: Dictionary of arguments to pass to the tool
        
    Returns:
        Extracted result from the tool call, or None if no content
        
    Raises:
        ConnectionError: If unable to connect to MCP server
        TimeoutError: If connection or tool call times out
        Exception: For other unexpected errors during tool execution
    """
    server_params = config.MCP_SERVER_PARAMS
    logger.info("MCP_SERVER_PARAMS: %s", server_params)
    # trust_env=False: prevents httpx from reading SSL_CERT_FILE / REQUESTS_CA_BUNDLE
    # from the environment. The cert path in backend/.env may not exist in every
    # container image; all MCP calls go to plain http:// endpoints so no custom
    # CA bundle is needed.
    async with httpx.AsyncClient(timeout=MCP_HTTP_TIMEOUT, follow_redirects=True, trust_env=False) as http_client:
        try:
            async with streamable_http_client(server_params, http_client=http_client) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    # Initialize the connection
                    await session.initialize()
                    #Call the tool
                    result = await session.call_tool(
                        tool_name,
                        tool_args,
                    )
                    logger.info("TOOL CALL RESULT: %s", result)

                    # Extract result based on content type
                    extracted_result: Any = None
                    if result.content:
                        # Check if content is a list and has items
                        if isinstance(result.content, list) and len(result.content) > 0:
                            first_content = result.content[0]

                            # Check content type and extract accordingly
                            if hasattr(first_content, 'type'):
                                if first_content.type == 'text':
                                    # Extract text content
                                    extracted_result = first_content.text

                                    # Try to parse as JSON if the text contains JSON data
                                    try:
                                        json_result = json.loads(extracted_result)
                                        # Unwrap double-encoded JSON (AWS MCP transport may pre-stringify)
                                        if isinstance(json_result, str):
                                            logger.info('json_result is string >>>>>>')
                                            try:
                                                json_result = json.loads(json_result)
                                            except (json.JSONDecodeError, TypeError):
                                                pass
                                        extracted_result = json_result
                                        logger.debug("EXTRACTED JSON RESULT: %s", json.dumps(json_result, indent=2))
                                        extracted_result = json_result
                                    except (json.JSONDecodeError, TypeError):
                                        # Not JSON, keep as text
                                        logger.debug("EXTRACTED TEXT RESULT: %s", extracted_result)
                                else:
                                    # Handle other content types if needed
                                    extracted_result = first_content
                                    logger.debug("EXTRACTED RESULT (type: %s): %s", first_content.type, extracted_result)
                            else:
                                extracted_result = first_content
                                logger.debug("EXTRACTED RESULT: %s", extracted_result)
                    else:
                        extracted_result = None
                        logger.info("NO CONTENT IN RESULT")

                    return extracted_result
        except ConnectionError as e:
            # Show full stack trace for unexpected errors on console
            traceback.print_exc()
            logger.error(f"Connection error while calling MCP tool '{tool_name}': {str(e)}")
            raise ConnectionError(f"Failed to connect to MCP server: {str(e)}") from e
        except TimeoutError as e:
            # Show full stack trace for unexpected errors on console
            traceback.print_exc()
            logger.error(f"Timeout error while calling MCP tool '{tool_name}': {str(e)}")
            raise TimeoutError(f"MCP tool call timed out: {str(e)}") from e
        except Exception as e:
            # Show full stack trace for unexpected errors on console
            traceback.print_exc()
            logger.error(f"Unexpected error while calling MCP tool '{tool_name}': {str(e)}", exc_info=True)
            raise

async def call_rest_api(path: str, method: str = "GET", params: dict[str, Any] | None = None, body: dict[str, Any] | None = None) -> Any:
    """
    Execute a direct HTTP REST call to the data-service.

    Args:
        path: URL path relative to DATA_SERVICE_URL (e.g. "/api/assessments/asmt_123")
        method: HTTP method (default: "GET")
        params: Optional query parameters
        body: Optional JSON request body (for POST/PUT)

    Returns:
        Parsed JSON response body

    Raises:
        httpx.HTTPStatusError: If the server returns a 4xx/5xx response
        Exception: For other unexpected errors during the request
    """
    url = f"{config.DATA_SERVICE_URL.rstrip('/')}/{path.lstrip('/')}"
    logger.info(f"REST API call: {method} {url}")
    try:
        # trust_env=False: prevents httpx from reading SSL_CERT_FILE from the environment.
        # All REST calls target plain http:// endpoints within the Docker network.
        async with httpx.AsyncClient(timeout=MCP_HTTP_TIMEOUT, follow_redirects=True, trust_env=False) as http_client:
            response = await http_client.request(method, url, params=params, json=body)
            response.raise_for_status()
            # Handle 204 No Content (e.g. risk-eval-sample endpoint) — no body to parse
            if response.status_code == 204 or not response.content:
                return None
            result: Any = response.json()
            logger.info(f"REST API response received from {url}")
            return result
    except httpx.HTTPStatusError as e:
        # Show full stack trace for unexpected errors on console
        traceback.print_exc()
        logger.error(f"REST API HTTP error for {method} {url}: {e.response.status_code} {e.response.text}")
        raise
    except Exception as e:
        # Show full stack trace for unexpected errors on console
        traceback.print_exc()
        logger.error(f"Unexpected error during REST API call to {url}: {str(e)}", exc_info=True)
        raise


def _repair_json_string(json_str: str) -> str:
    """
    Attempt to repair common JSON formatting issues.
    
    Args:
        json_str: Potentially malformed JSON string
        
    Returns:
        Repaired JSON string
    """
    import re

    # Remove any leading/trailing whitespace
    json_str = json_str.strip()

    # Remove markdown code blocks if present
    if json_str.startswith('```'):
        # Find the first newline after opening ```
        first_newline = json_str.find('\n')
        if first_newline != -1:
            json_str = json_str[first_newline + 1:]
        # Remove closing ```
        if json_str.endswith('```'):
            json_str = json_str[:-3].rstrip()

    # Remove any text before the first '{' and after the last '}'
    if '{' in json_str and '}' in json_str:
        start_idx = json_str.find('{')
        end_idx = json_str.rfind('}') + 1
        json_str = json_str[start_idx:end_idx]

    # Fix common LLM error: "Sl No. 1" → "Sl No.": 1
    # Pattern: "Sl No. X" where X is a number (missing colon between key and value)
    json_str = re.sub(r'"Sl No\.\s*(\d+)"', r'"Sl No.": \1', json_str)

    # Fix common LLM error: "Sl No.": 1: 1 → "Sl No.": 1
    # Pattern: duplicate value after colon (e.g., ": 1: 1" should be ": 1")
    json_str = re.sub(r'"Sl No\.":\s*(\d+):\s*\d+', r'"Sl No.": \1', json_str)

    return json_str

def format_assistant_response(analyze_result: Any) -> tuple[bool, Any]:
        # Parse and validate JSON output from agent
        if isinstance(analyze_result, dict):
            # Result is already a dictionary (pre-parsed)
            logger.info("Result is already a dictionary")
            parsed_data = analyze_result

            # Validate structure
            if 'data' in parsed_data:
                data_list = parsed_data['data']
                if isinstance(data_list, list):
                    # Filter out any non-dict items
                    valid_items = [item for item in data_list if isinstance(item, dict)]
                    if len(valid_items) == len(data_list):
                        logger.info(f"Valid dict format with {len(data_list)} rows")
                    else:
                        logger.warning(f"Filtered out {len(data_list) - len(valid_items)} non-dict items")

                    # Return True even for empty data list - it's valid structure
                    logger.info(f"Returning parsed dict with {len(valid_items)} valid items")
                    return True, parsed_data

            # Has dict but no 'data' key - still return it
            logger.warning("Dict has no 'data' key, returning as-is")
            return True, parsed_data

        elif isinstance(analyze_result, str):
            try:
                # Attempt to parse JSON from the result string using json.loads()
                logger.info("Attempting to parse agent output as JSON...")
                logger.debug(f"Raw string (first 500 chars): {analyze_result[:500]}")

                # Repair the JSON string (extract and clean)
                json_str = _repair_json_string(analyze_result)
                logger.debug(f"Repaired JSON (first 500 chars): {json_str[:500]}")

                # Parse JSON string to Python dictionary
                try:
                    parsed_data = json.loads(json_str)
                    logger.info("Successfully parsed JSON from agent output")
                    return True, parsed_data
                except json.JSONDecodeError as parse_error:
                    # Log the specific error location for debugging
                    logger.error(f"JSON parsing failed at line {parse_error.lineno}, column {parse_error.colno}: {parse_error.msg}")
                    logger.error(f"Error context: ...{json_str[max(0, parse_error.pos-50):parse_error.pos+50]}...")

                    # Try alternative: use json.loads with strict=False
                    try:
                        parsed_data = json.loads(json_str, strict=False)
                        logger.info("Successfully parsed JSON with strict=False")
                        return True, parsed_data
                    except Exception:
                        logger.error("strict=False parsing also failed")
                        return False, None

            except json.JSONDecodeError as e:
                # JSON parsing failed - result is plain text
                logger.error(f"JSON parsing failed: {e}. Returning as text response.")
                logger.error(f"Failed to parse LLM output. First 500 chars: {analyze_result[:500]}")
                return False, None

            except Exception as e:
                # Unexpected error during parsing/validation
                logger.error(f"Unexpected error during JSON processing: {e}", exc_info=True)
                # Fallback to text response to ensure API doesn't fail
                return False, None

        else:
            # Result is not a string or dict (unexpected)
            logger.warning(f"Result is not a string or dict: {type(analyze_result)}")
            return False, None
