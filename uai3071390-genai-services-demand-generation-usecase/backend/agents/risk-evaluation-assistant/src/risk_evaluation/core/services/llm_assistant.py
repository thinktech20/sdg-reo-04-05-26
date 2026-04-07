"""
LLM Assistant Service Module.

Orchestrates parallel LLM calls across multiple channels for risk assessment.
Splits N user prompts into configurable parallel channels, processes each channel
serially, and collates all results.
"""

from __future__ import annotations

import asyncio
import math
import os,json,re
import time
from pathlib import Path
from typing import Any

from risk_evaluation.core.agent_factory import RiskAnalysisAssistant
from risk_evaluation.core.config.logger_config import get_logger

logger = get_logger(__name__)

# Default concurrency configuration
DEFAULT_NUM_CHANNELS = 7


class LLMAssistant:
    """
    Service class for executing parallel LLM calls across multiple channels.

    Splits a list of user prompts into N channels (default: 3), runs each channel
    concurrently via asyncio, and processes prompts within each channel serially.
    """

    def __init__(
        self,
        model_name: str | None = None,
        num_channels: int = DEFAULT_NUM_CHANNELS,
    ):
        """
        Initialize the LLM Assistant.

        Args:
            model_name: The LLM model name (optional, defaults to .env config).
            num_channels: Number of parallel channels for LLM calls (default: 3).
        """
        self.assistant = RiskAnalysisAssistant(model_name=model_name)
        self.num_channels = num_channels
        try:
            self.system_prompt = self.assistant.load_system_prompt()
        except Exception as e:
            logger.error("Failed to load system prompt: %s", e)
            raise
        logger.info(
            "LLMAssistant initialized with %d channels", self.num_channels
        )

    async def _process_channel(
        self,
        channel_id: int,
        system_prompt: str,
        user_prompts: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        """
        Process a single channel's user prompts serially.

        Each prompt is sent to the LLM one at a time within this channel.
        Results are collected in order.

        Args:
            channel_id: Identifier for this channel (for logging).
            system_prompt: The system prompt shared across all calls.
            user_prompts: List of dicts, each containing at minimum
                          {"issue_id": str, "user_prompt": str}.

        Returns:
            List of result dicts: [{"issue_id": str, "response": str | None, "error": str | None}, ...]
        """
        results: list[dict[str, Any]] = []
        total = len(user_prompts)
        channel_start = time.perf_counter()
        logger.info("Channel %d: starting %d LLM calls", channel_id, total)

        for idx, prompt_item in enumerate(user_prompts, start=1):
            issue_id = prompt_item["issue_id"]
            user_prompt = prompt_item["user_prompt"]
            logger.debug(f"User Prompt for issue_id=%s: %s", issue_id, user_prompt[:600])  # Log first 600 chars
            logger.info(
                "Channel %d: processing %d/%d (issue_id=%s)",
                channel_id, idx, total, issue_id,
            )
            # Retry logic: try up to 3 times with 5s wait between attempts
            last_exception = None
            for attempt in range(1, 4):
                try:
                    response = await self.assistant.invoke_with_prompt(
                        system_prompt=system_prompt,
                        user_prompt_for_issue=user_prompt,
                    )
                    results.append({
                        "issue_id": issue_id,
                        "response": response,
                        "error": None,
                    })
                    logger.info(
                        "Channel %d: completed %d/%d (issue_id=%s) on attempt %d",
                        channel_id, idx, total, issue_id, attempt,
                    )
                    break
                except Exception as e:
                    last_exception = e
                    logger.error(
                        "Channel %d: failed %d/%d (issue_id=%s) on attempt %d: %s",
                        channel_id, idx, total, issue_id, attempt, e,
                    )
                    if attempt < 3:
                        # Wait 5 seconds before next retry
                        await asyncio.sleep(5)
            else:
                # All attempts failed
                results.append({
                    "issue_id": issue_id,
                    "response": None,
                    "error": str(last_exception),
                })
                logger.error(
                    "Channel %d: all %d attempts failed for %d/%d (issue_id=%s): %s",
                    channel_id, 3, idx, total, issue_id, last_exception,
                )

        channel_elapsed = time.perf_counter() - channel_start
        logger.info("Channel %d: finished all %d calls in %.2f seconds", channel_id, total, channel_elapsed)
        return results

    @staticmethod
    def _load_user_prompts_from_disk(esn: str) -> list[dict[str, str]]:
        """
        Read all user_prompt_<issue_id>.txt files from run_outputs/<esn>/.

        Each filename encodes the issue_id:
            user_prompt_<issue_id>.txt

        Args:
            esn: Equipment serial number (subfolder name under RUN_ARTIFACTS_DIR).

        Returns:
            List of {"issue_id": str, "user_prompt": str} dicts, one per file.
        """
        run_dir = Path(os.getenv("RUN_ARTIFACTS_DIR", "/tmp/run")) / esn
        if not run_dir.is_dir():
            raise FileNotFoundError(f"Run directory not found: {run_dir}")

        user_prompts: list[dict[str, str]] = []
        for prompt_file in sorted(run_dir.glob("user_prompt_*.txt")):
            try:
                # Extract issue_id from filename: user_prompt_<issue_id>.txt
                issue_id = prompt_file.stem.removeprefix("user_prompt_")
                content = prompt_file.read_text(encoding="utf-8")
                user_prompts.append({"issue_id": issue_id, "user_prompt": content})
                logger.info("Loaded user prompt for issue_id=%s from %s", issue_id, prompt_file)
            except Exception as e:
                logger.error("Failed to read prompt file %s: %s", prompt_file, e)

        logger.info("Loaded %d user prompts from %s", len(user_prompts), run_dir)
        return user_prompts

    async def run_parallel_llm_calls(
        self,
        esn: str,
    ) -> list[dict[str, Any]]:
        """
        Execute LLM calls across parallel channels and collate results.

        Reads all user_prompt_<issue_id>.txt files from run_outputs/<esn>/,
        splits them across self.num_channels channels, and processes in parallel.

        The system prompt is loaded once from prompt_lib/system_prompt.txt
        during __init__ and shared across all channels.

        Args:
            esn: Equipment serial number — used to locate the run_outputs/<esn>/ folder
                 containing user_prompt_*.txt files.

        Returns:
            Collated list of result dicts from all channels, preserving
            the original order of user_prompts:
            [{"issue_id": str, "response": str | None, "error": str | None}, ...]
        """
        try:
            user_prompts = self._load_user_prompts_from_disk(esn)
        except FileNotFoundError as e:
            logger.error("Cannot run parallel LLM calls: %s", e)
            return []

        if not user_prompts:
            logger.warning("No user prompt files found for esn=%s, returning empty results", esn)
            return []

        total_start = time.perf_counter()
        total = len(user_prompts)
        num_channels = min(self.num_channels, total)
        chunk_size = math.ceil(total / num_channels)

        logger.info(
            "Splitting %d LLM calls across %d channels (%d per channel)",
            total, num_channels, chunk_size,
        )

        # Split user_prompts into channel-sized chunks
        channel_chunks: list[list[dict[str, str]]] = [
            user_prompts[i : i + chunk_size]
            for i in range(0, total, chunk_size)
        ]

        # Launch all channels concurrently
        channel_tasks = [
            self._process_channel(
                channel_id=ch_idx,
                system_prompt=self.system_prompt,
                user_prompts=chunk,
            )
            for ch_idx, chunk in enumerate(channel_chunks)
        ]

        channel_results = await asyncio.gather(*channel_tasks, return_exceptions=True)

        # Collate results from all channels in order
        collated: list[dict[str, Any]] = []
        for ch_idx, result in enumerate(channel_results):
            if isinstance(result, BaseException):
                logger.error("Channel %d raised an exception: %s", ch_idx, result)
                # Mark all prompts in this channel as failed
                for prompt_item in channel_chunks[ch_idx]:
                    collated.append({
                        "issue_id": prompt_item["issue_id"],
                        "response": None,
                        "error": str(result),
                    })
            else:
                collated.extend(result)

        total_elapsed = time.perf_counter() - total_start
        logger.info(
            "All channels complete in %.2f seconds. Total results: %d (success: %d, failed: %d)",
            total_elapsed,
            len(collated),
            sum(1 for r in collated if r["error"] is None),
            sum(1 for r in collated if r["error"] is not None),
        )
        logger.info("LLMAssistant run_parallel_llm_calls finished. Collated results: %s", collated)
        return collated
