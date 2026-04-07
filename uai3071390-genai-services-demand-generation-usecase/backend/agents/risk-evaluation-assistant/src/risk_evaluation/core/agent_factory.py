"""Agent factory for the Risk Evaluation Assistant (A1).

No Agent is maintained in the application.
Assistant is an impromptu agent created per request, and MCP tools are called via HTTP.
A1 - A3 are stateless (LangGraph owns session) — no S3SessionManager.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from enum import Enum
from typing import Any

import boto3
import pandas as pd

#Load the libraries
import yaml
from strands import Agent
from strands.models.litellm import LiteLLMModel

from risk_evaluation import config

#Initialize logger
logger = logging.getLogger(__name__)

# Disable SSL verification for proxy connections
os.environ['SSL_VERIFY'] = 'False'

# ==================== Stage Configuration ====================

class AssistantStage(Enum):
    """Enum defining different stages of the risk analysis assistant."""
    COMPONENT_VALIDATION = "component_validation"  # Validate and classify components
    SEVERITY_DETERMINATION = "severity_determination"  # Determine risk severity
    COMBINED_ANALYSIS = "combined_analysis"  # Combined filtering and severity in one prompt

# Configuration mapping for each stage
STAGE_CONFIG: dict[AssistantStage, dict[str, Any]] = {
    AssistantStage.COMPONENT_VALIDATION: {
        "reference_loader": "_load_component_reference_data",
        "prompt_keys": {
            "data_key": "tool_results",
            "reference_key": "component_reference_data"
        }
    },
    AssistantStage.SEVERITY_DETERMINATION: {
        "reference_loader": "_load_severity_mapping_data",
        "prompt_keys": {
            "data_key": "valid_results",
            "reference_key": "severity_mapping_rules"
        }
    },
    AssistantStage.COMBINED_ANALYSIS: {
        "reference_loaders": ["_load_component_reference_data", "_load_severity_mapping_data"],
        "prompt_keys": {
            "data_key": "tool_results",
            "component_reference_key": "component_reference_data",
            "severity_reference_key": "severity_mapping_rules"
        }
    }
}

def build_model() -> LiteLLMModel:
    """Instantiate LiteLLMModel once at startup (shared across requests)."""
    logger.info(
        "Building LiteLLMModel",
        extra={"base_url": config.LITELLM_API_BASE, "model_id": config.LITELLM_MODEL_ID},
    )
    litellm_proxy_api_key = config.LITELLM_PROXY_API_KEY
    return LiteLLMModel(
        client_args={
        "api_key": litellm_proxy_api_key,
        "base_url": config.LITELLM_API_BASE,
        "use_litellm_proxy": True
    },
    model_id=config.LITELLM_MODEL_ID
    )


def build_boto_session() -> boto3.Session:
    """Build a boto3 Session (shared across requests)."""
    return boto3.Session(region_name=config.AWS_REGION)


def build_agent(
    model: LiteLLMModel,
    tools: list[Any],
    system_prompt: str,
) -> Agent:
    """Create a per-request Strands Agent.

    A1 has no session state — called once per orchestrator invocation.
    A new Agent is created per-request because Strands Agent uses an internal
    threading.Lock and cannot safely be shared across concurrent requests.
    """
    return Agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        callback_handler=None,
    )

# Langchain imports
from langchain_core.prompts import PromptTemplate


class RiskAnalysisAssistant:
    """
    Assistant class for risk analysis using MCP tools and Gemini LLM.
    """
    def __init__(self, model_name: str | None = None):
        """
        Initialize the Risk Analysis Assistant.

        Args:
            model_name: The name of the Gemini model to use (optional, defaults to .env)
        """

        # Load model name from .env if not provided
        if model_name is None:
            model_name = config.LITELLM_MODEL_ID

        self.model_name = model_name
        self.api_key = config.LITELLM_PROXY_API_KEY
        self.api_base = config.LITELLM_API_BASE

    def load_system_prompt(self, prompt_filename: str = "system_prompt.txt") -> str:
        """Load the system prompt text from a file in prompt_lib folder."""
        prompt_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'prompt_lib',
            prompt_filename
        )
        try:
            with open(prompt_file, encoding='utf-8') as f:
                content = f.read()
            logger.info(f"Loaded system prompt from {prompt_file}")
            return content
        except Exception as e:
            logger.error(f"Error loading system prompt from {prompt_file}: {e}")
            raise e

    async def invoke_with_prompt(
        self,
        system_prompt: str,
        user_prompt_for_issue: str,
    ) -> str:
        """
        Invoke the LLM with explicit system and user prompts.
        Args:
            system_prompt: The system prompt for the LLM agent.
            user_prompt_for_issue: The user prompt containing issue-specific context.
        Returns:
            The LLM response text.
        """
        model = build_model()
        agent = build_agent(
            model=model,
            tools=[],
            system_prompt=system_prompt,
        )
        try:
            result = await agent.invoke_async(user_prompt_for_issue)
            reply_text = result.message["content"][0]["text"]
            return reply_text
        except Exception as e:
            logger.error(f"Error during Strands Agent invocation: {e}")
            raise e
        finally:
            agent.cleanup()

    def _load_prompt_template(self, prompt_filename: str) -> PromptTemplate:
        """Load prompt template from YAML file in prompt_lib folder."""
        prompt_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
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

    def _load_component_reference_data(self) -> str:
        """Load component reference CSV as dataframe and format for prompt."""
        csv_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'prompt_lib',
            'component_reference_data.csv'
        )

        logger.info(f"Attempting to load component reference data from: {csv_file}")
        logger.info(f"File exists: {os.path.exists(csv_file)}")
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.info(f"__file__ location: {os.path.abspath(__file__)}")

        # Read first line to debug
        try:
            with open(csv_file, encoding='utf-8') as f:
                first_line = f.readline().strip()
                logger.info(f"First line of CSV: {repr(first_line)}")
                logger.info(f"First line bytes: {first_line.encode('utf-8')!r}")
        except Exception as debug_err:
            logger.error(f"Could not read file for debugging: {debug_err}")

        try:
            # Load CSV as pandas dataframe with tab delimiter
            df = pd.read_csv(csv_file, delimiter='\t', encoding='utf-8')

            # Strip whitespace from column names
            df.columns = df.columns.str.strip()

            logger.info(f"Loaded component reference data: {len(df)} rows, columns: {list(df.columns)}")

            # Verify required columns exist
            if 'Type' not in df.columns:
                raise ValueError(f"Missing 'Type' column. Found columns: {list(df.columns)}")
            if 'Component' not in df.columns:
                raise ValueError(f"Missing 'Component' column. Found columns: {list(df.columns)}")

            # Strip whitespace from Type column values
            df['Type'] = df['Type'].str.strip()

            logger.info(f"Unique Type values: {df['Type'].unique().tolist()}")

            # Format as markdown table for LLM
            markdown_table = "| Component | Type |\n"
            markdown_table += "|-----------|------|\n"

            for _, row in df.iterrows():
                component = str(row.get('Component', '')).strip()
                comp_type = str(row.get('Type', '')).strip()
                markdown_table += f"| {component} | {comp_type} |\n"

            # Add summary information
            stator_count = len(df[df['Type'] == 'Stator'])
            rotor_count = len(df[df['Type'] == 'Rotor'])

            summary = "\n\nSUMMARY:\n"
            summary += f"- Total components: {len(df)}\n"
            summary += f"- Stator components: {stator_count}\n"
            summary += f"- Rotor components: {rotor_count}\n"
            summary += "\nCLASSIFICATION RULE:\n"
            summary += "- If evidence mentions any component with Type = 'Stator' → Classify as Stator\n"
            summary += "- If evidence mentions any component with Type = 'Rotor' → Classify as Rotor\n"

            logger.debug(f"Component reference stats - Stator: {stator_count}, Rotor: {rotor_count}")
            return markdown_table + summary

        except Exception as e:
            error_msg = f"Error loading component reference data from '{csv_file}': {type(e).__name__}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return f"Component reference data not available. Error: {str(e)}"

    def _load_severity_mapping_data(self) -> str:

        """Load severity mapping JSON and return as formatted string for prompt."""
        json_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'prompt_lib',
            'issue_and_severity_mapping.json'
        )

        try:
            with open(json_file, encoding='utf-8') as f:
                severity_data = json.load(f)

            logger.info(f"Loaded severity mapping data: {len(severity_data)} rules from {json_file}")
            return json.dumps(severity_data, indent=2, ensure_ascii=False)

        except Exception as e:
            error_msg = f"Error loading severity mapping data from '{json_file}': {type(e).__name__}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return f"Severity mapping data not available. Error: {str(e)}"


    async def run_parallel_assistant(
        self,
        tool_results_fsr: dict[str, Any],
        tool_results_er: dict[str, Any],
        prompt_filename_a: str,
        prompt_filename_b: str,
        input_params: dict[str, Any] | None = None
    ) -> tuple[str, str]:
        """
        Run two LLM assistant calls in parallel for component validation.
        
        Executes both FSR and ER tool result analysis concurrently using asyncio.gather,
        improving performance by parallelizing independent LLM invocations.
        
        Args:
            tool_results_fsr: FSR (Field Service Report) tool results to analyze
            tool_results_er: ER (Engineering Report) tool results to analyze
            prompt_filename_a: Prompt template filename for FSR analysis
            prompt_filename_b: Prompt template filename for ER analysis
            input_params: Optional dictionary containing 'query' and 'component_type'
            
        Returns:
            Tuple[str, str]: A tuple containing (response_a, response_b) where:
                - response_a: LLM response for FSR analysis
                - response_b: LLM response for ER analysis
                
        Raises:
            Exception: If either LLM invocation fails (return_exceptions=False)
        """
         # Run both LLM calls in parallel for component validation stage
        response_a, response_b = await asyncio.gather(
            self.invoke_assistant(
                tool_results=tool_results_fsr,
                stage=AssistantStage.COMPONENT_VALIDATION,
                prompt_filename=prompt_filename_a,
                input_params=input_params
            ),
            self.invoke_assistant(
                tool_results=tool_results_er,
                stage=AssistantStage.COMPONENT_VALIDATION,
                prompt_filename=prompt_filename_b,
                input_params=input_params
            ),
            return_exceptions=False
        )
        return response_a, response_b

    async def invoke_assistant(
        self,
        tool_results: dict[str, Any],
        stage: AssistantStage,
        prompt_filename: str,
        input_params: dict[str, Any] | None = None
    ) -> str:
        """
        Create the assistant with LLM, tools, and prompt template based on application stage.
        
        Args:
            tool_results: Tool results to analyze
            stage: AssistantStage enum indicating which stage of processing
            prompt_filename: Name of the prompt template file
            input_params: Dictionary with keys 'query' and 'component_type'
        """
        # Parse input parameters dictionary
        if input_params is None:
            input_params = {}

        query = input_params.get('query', '')
        component_type = input_params.get('component_type', '')

        # Load prompt template from YAML file
        prompt_template = self._load_prompt_template(prompt_filename)

        # Get stage configuration
        stage_config = STAGE_CONFIG[stage]

        # Get prompt variable keys for this stage
        data_key = stage_config["prompt_keys"]["data_key"]

        # Build prompt variables dynamically based on stage configuration
        prompt_vars: dict[str, Any] = {
            data_key: tool_results,
            "query": query,
            "component_type": component_type,
        }

        # Handle combined analysis stage with multiple reference loaders
        if stage == AssistantStage.COMBINED_ANALYSIS:
            # Load both component and severity reference data
            component_ref = self._load_component_reference_data()
            severity_ref = self._load_severity_mapping_data()
            prompt_vars[stage_config["prompt_keys"]["component_reference_key"]] = component_ref
            prompt_vars[stage_config["prompt_keys"]["severity_reference_key"]] = severity_ref
        else:
            # Single reference loader for other stages
            loader_method_name = stage_config["reference_loader"]
            loader_method = getattr(self, loader_method_name)
            reference_data = loader_method()
            reference_key = stage_config["prompt_keys"]["reference_key"]
            prompt_vars[reference_key] = reference_data

        # Format prompt with variables
        formatted_prompt = prompt_template.format(**prompt_vars)


        #logger.info(f"Formatted Prompt: {formatted_prompt}")

        # Create LiteLLMModel instance with proxy settings
        model = build_model()

        # Build Strands Agent using the factory function
        agent = build_agent(
            model=model,
            tools=[],
            system_prompt="You are a risk analysis assistant. Analyze the provided data and return a JSON response."
        )

        # Invoke the agent with the formatted prompt string
        try:
            result = await agent.invoke_async(formatted_prompt)
            reply_text = result.message["content"][0]["text"]
            #logger.info(f"LLM Response: {reply_text}")
            return reply_text
        except Exception as e:
            logger.error(f"Error during Strands Agent invocation: {e}")
            raise e
        finally:
            # Clean up agent resources
            agent.cleanup()
