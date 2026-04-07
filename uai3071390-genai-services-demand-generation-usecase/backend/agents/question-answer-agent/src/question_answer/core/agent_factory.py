"""Agent factory — builds and runs a per-request Strands Agent via MCPClient.

WHY per-request:
  Strands Agent uses a threading.Lock that raises ConcurrencyException when two
  callers hit the same instance simultaneously.  FastAPI serves many concurrent
  requests, so sharing one Agent instance would serialize all chat requests.
  Instead we build a fresh Agent per request — cheap, just wires references together.

WHY MCPClient inside the job:
  MCPClient must stay open for the full duration of the agent's tool calls.
  We open it inside run_agent and close it on exit.

MCPClient API (verified against strands-agents>=0.1.0):
    Constructor: MCPClient(transport_callable) where transport_callable is a callable
    returning an async context manager.
    Context manager: with client (sync) — tools available as client.list_tools_sync()
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.models.litellm import LiteLLMModel
from strands.tools.mcp import MCPClient
from strands.types.content import Message

from question_answer import config
from question_answer.prompts import get_system_prompt
from question_answer.tools.registry import filter_by_persona, get_tool_name

logger = logging.getLogger(__name__)

# Number of conversation turns kept in context window
_WINDOW_SIZE = 40
_DEBUG_PAYLOAD_LIMIT = 1500

os.environ["SSL_VERIFY"] = "False"

def _env_flag(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() == "true"


def _s3_endpoint_url() -> str:
    return os.getenv("S3_ENDPOINT_URL", config.S3_ENDPOINT_URL)


def _build_mcp_transport() -> Any:
    return lambda: streamablehttp_client(config.MCP_SERVER_URL)


def _serialize_debug_payload(payload: Any) -> str:
    text = json.dumps(payload, default=str, ensure_ascii=True)
    if len(text) <= _DEBUG_PAYLOAD_LIMIT:
        return text
    return f"{text[:_DEBUG_PAYLOAD_LIMIT]}...<truncated>"


def _strands_callback(**kwargs: Any) -> None:
    """Strands agent callback — logs tool calls at INFO and details at DEBUG."""
    reasoning_text = kwargs.get("reasoningText")
    if reasoning_text:
        logger.debug("strands reasoning=%s", reasoning_text)

    current_tool_use = kwargs.get("current_tool_use")
    if current_tool_use:
        tool_name = current_tool_use.get("name", "unknown")
        logger.info("strands tool_call: name=%s", tool_name)
        logger.debug("strands tool_use=%s", _serialize_debug_payload(current_tool_use))

    data = kwargs.get("data")
    if data:
        logger.debug("strands text_chunk=%s", data)

    event = kwargs.get("event")
    if event:
        tool_use = event.get("contentBlockStart", {}).get("start", {}).get("toolUse")
        if tool_use:
            logger.debug("strands tool_event=%s", _serialize_debug_payload(tool_use))

    message = kwargs.get("message")
    if message:
        # Log tool errors at INFO level for troubleshooting
        for block in message.get("content", []):
            if isinstance(block, dict) and "toolResult" in block:
                tr = block["toolResult"]
                if tr.get("status") == "error":
                    error_text = " ".join(
                        c.get("text", "") for c in tr.get("content", []) if isinstance(c, dict)
                    ).strip()
                    logger.info(
                        "strands tool_error: toolUseId=%s error=%s",
                        tr.get("toolUseId", "unknown"),
                        error_text[:500] if error_text else "no details",
                    )
        logger.debug("strands message=%s", _serialize_debug_payload(message))

    result = kwargs.get("result")
    if result:
        logger.debug("strands result=%s", _serialize_debug_payload(result))


def _extract_text_content(message: Message) -> str:
    """Extract assistant text from Strands response content blocks.

    Some Strands/LiteLLM responses return blocks as {"text": "..."} without
    an explicit {"type": "text"} marker. Accept both shapes.
    """
    content_blocks = message.get("content", [])
    text_blocks = [block["text"] for block in content_blocks if isinstance(block, dict) and "text" in block]
    if text_blocks:
        return "\n".join(text_blocks)

    raise RuntimeError(f"Agent returned no text content: {message}")


def build_model() -> LiteLLMModel:
    """Construct the shared LiteLLMModel (called once at lifespan startup)."""
    return LiteLLMModel(
        client_args={
            "api_key": config.LITELLM_API_KEY,
            "base_url": config.LITELLM_API_BASE,
        },
        model_id=config.LITELLM_MODEL,
        params={
            "stream": config.LITELLM_STREAM,
            "temperature": config.TEMPERATURE,
            "max_tokens": config.MAX_TOKENS,
        },
    )


def build_boto_session() -> boto3.Session:
    """Construct the shared boto3 Session (called once at lifespan startup)."""
    if _env_flag("S3_LOCAL_MODE", config.S3_LOCAL_MODE):
        return boto3.Session(
            aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID", config.S3_ACCESS_KEY_ID),
            aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY", config.S3_SECRET_ACCESS_KEY),
            region_name=config.SESSION_S3_REGION,
        )
    return boto3.Session(region_name=config.SESSION_S3_REGION)


def build_agent(
    model: LiteLLMModel,
    boto_session: boto3.Session,
    persona: str = "RE",
    user_sso_id: str | None = None,
    session_id: str | None = None,
    tools: list[Any] | None = None,
) -> Agent:
    """Build and return a Strands Agent without invoking it.

    Wires S3SessionManager when session_id is provided. Called by run_agent()
    per request so that agent construction can be tested independently of
    MCP and prompt invocation.

    Args:
        model:        Shared LiteLLMModel (built once at startup).
        boto_session: Shared boto3.Session (built once at startup).
        persona:      "RE" or "OE" — selects the system prompt.
        user_sso_id:  SSO subject claim for S3 prefix namespacing.
        session_id:   S3 session key for conversation persistence.
        tools:        Persona-filtered tool list from MCPClient.

    Returns:
        Configured Strands Agent (not yet invoked).
    """
    # Session persistence via S3
    session_manager = None
    if session_id:
        from strands.session.s3_session_manager import S3SessionManager  # noqa: PLC0415

        prefix = f"qna-agent/{user_sso_id or 'anonymous'}"
        if _env_flag("S3_LOCAL_MODE", False):
            # Point boto3 at the local MinIO endpoint without mutating the global
            # environment — pass the endpoint URL directly to the boto3 session.
            os.environ["AWS_ENDPOINT_URL_S3"] = _s3_endpoint_url()

        session_manager = S3SessionManager(
            session_id=session_id,
            bucket=config.SESSION_S3_BUCKET_NAME,
            prefix=prefix,
            boto_session=boto_session,
            region_name=config.SESSION_S3_REGION,
        )

    return Agent(
        model=model,
        system_prompt=get_system_prompt(persona),
        tools=tools or [],
        session_manager=session_manager,
        conversation_manager=SlidingWindowConversationManager(window_size=_WINDOW_SIZE),
        callback_handler=_strands_callback,
    )


async def run_agent(
    prompt: str,
    persona: str,
    model: LiteLLMModel,
    boto_session: boto3.Session,
    session_id: str | None = None,
    user_sso_id: str | None = None,
) -> str:
    """Open MCP client, filter tools by persona, build agent, invoke, return reply.

    Owns the full per-request lifecycle:
    MCPClient open → filter tools → build_agent() → invoke_async → MCPClient close.

    Args:
        prompt:       User question.
        persona:      "RE" or "OE" — determines which tools are available.
        model:        Shared LiteLLMModel (built once at startup).
        boto_session: Shared boto3.Session (built once at startup).
        session_id:   S3 session key for conversation persistence.
        user_sso_id:  SSO subject claim for S3 prefix namespacing.

    Returns:
        Agent reply as plain text.
    """
    with MCPClient(_build_mcp_transport()) as mcp_client:
        logger.info("MCP connecting: url=%s", config.MCP_SERVER_URL)
        # Get tools from MCP server and filter to persona-allowed subset
        all_tools = mcp_client.list_tools_sync()
        all_tool_names = [get_tool_name(tool) or repr(tool) for tool in all_tools]
        tools = filter_by_persona(all_tools, persona)
        filtered_tool_names = [get_tool_name(tool) or repr(tool) for tool in tools]

        logger.info(
            "agent_factory: fetched mcp tools count=%d names=%s",
            len(all_tool_names),
            all_tool_names,
        )
        logger.info(
            "agent_factory: filtered tools persona=%s count=%d names=%s",
            persona,
            len(filtered_tool_names),
            filtered_tool_names,
        )

        system_prompt = get_system_prompt(persona)
        logger.info(
            "agent_factory: building agent persona=%s tools=%d session_id=%s",
            persona,
            len(tools),
            session_id,
        )
        logger.debug("agent_factory: system_prompt=%s", system_prompt)
        logger.debug("agent_factory: user_prompt=%s", prompt)

        agent = build_agent(
            model=model,
            boto_session=boto_session,
            persona=persona,
            user_sso_id=user_sso_id,
            session_id=session_id,
            tools=tools,
        )

        try:
            result = await agent.invoke_async(prompt)

            # Log post-invocation diagnostics at INFO for troubleshooting
            metrics = result.metrics
            tools_called = {
                name: {"calls": m.call_count, "success": m.success_count, "errors": m.error_count}
                for name, m in metrics.tool_metrics.items()
            }
            logger.info(
                "agent_factory: invocation complete persona=%s session_id=%s "
                "cycles=%d tools_called=%s stop_reason=%s "
                "tokens=%s",
                persona,
                session_id,
                metrics.cycle_count,
                tools_called or "none",
                result.stop_reason,
                dict(metrics.accumulated_usage) if metrics.accumulated_usage else "n/a",
            )

            return _extract_text_content(result.message)
        finally:
            agent.cleanup()
