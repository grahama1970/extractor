"""
Module: litellm_call.py
Description: Model Context Protocol (MCP) integration

External Dependencies:
- litellm: https://docs.litellm.ai/
- pydantic: https://docs.pydantic.dev/
- loguru: https://loguru.readthedocs.io/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

from types import SimpleNamespace
import litellm
import async_timeout
from deepmerge import always_merger
from pydantic import BaseModel, Field
import asyncio
import os
import copy
from typing import Any, AsyncGenerator, Dict, Type, Union
from pydantic import BaseModel
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from .multimodal_utils import (
    format_multimodal_messages,
    is_multimodal,
)
from .initialize_litellm_cache import initialize_litellm_cache # Added import

# Load environment variables Globally
# Environment variables should be loaded by the application entry point or config management
# project_dir = get_project_root() # Removed
# load_env_file() # Removed


# Helper function to validate and update LLM config
def validate_update_config(
    config: Dict[str, Any], insert_into_db: bool = False
) -> Dict[str, Any]:
    """
    Validates and updates LLM config to meet requirements for JSON/structured responses.

    Args:
        llm_config: The LLM configuration dictionary

    Returns:
        Dict[str, Any]: Updated LLM config with proper JSON formatting instructions

    Raises:
        ValueError: If JSON requirements cannot be met
    """
    llm_config = config.get("llm_config", {})
    directories = config.get("directories", {})
    if not llm_config.get("messages", []):
        raise ValueError("A message object is required to query the LLM")

    response_format = llm_config.get("response_format")
    requires_json = response_format == "json" or (
        isinstance(response_format, type) and issubclass(response_format, BaseModel)
    )

    if requires_json:
        messages = llm_config.get("messages", []).copy()
        system_messages = [msg for msg in messages if msg.get("role") == "system"]

        if not system_messages:
            # Add a new system message if none exists
            messages.insert(
                0,
                {
                    "role": "system",
                    "content": "You must return your response as a well-formatted JSON object.",
                },
            )
        else:
            # Update existing system message if JSON instruction is missing
            system_content = system_messages[0].get("content", "").lower()
            json_instruction_keywords = ["json", "well-formatted", "well formatted"]

            if not any(
                keyword in system_content for keyword in json_instruction_keywords
            ):
                system_messages[0]["content"] = (
                    "You must return your response as a well-formatted JSON object. "
                    + system_messages[0]["content"]
                )

        # Check for multimodal content
        if is_multimodal(messages):
            # hardcoded for now
            image_directory = directories.get("image_directory", "")
            max_size_kb = llm_config.get("max_image_size_kb", 500)
            messages = format_multimodal_messages(
                messages, image_directory, max_size_kb
            )

        llm_config = copy.deepcopy(llm_config)
        llm_config["messages"] = messages

    return llm_config


# Main
@retry(
    wait=wait_exponential(multiplier=1, min=4, max=10),  # Exponential backoff
    stop=stop_after_attempt(3),  # Max 3 retries
    retry=retry_if_exception_type(Exception),  # Retry on any exception
)
async def litellm_call(config: Dict) -> Union[BaseModel, Dict[str, Any], str]:
    try:
        llm_config = config.get("llm_config", {})
        directories = config.get("directories", {})

        llm_config = validate_update_config(config)

        # Default to plain text if response_format is not provided
        response_format = llm_config.get("response_format", None)

        api_params = {
            "model": llm_config.get("model", "openai/gpt-4o-mini"),
            "messages": config["llm_config"]["messages"], # Use messages passed directly into the function
            "temperature": llm_config.get("temperature", 0.2),
            "max_tokens": llm_config.get("max_tokens", 1000),
            "stream": llm_config.get("stream", False),
            "caching": llm_config.get("caching", True),
            "metadata": {"request_id": llm_config.get("request_id"), "hidden": True},
        }
        if llm_config.get("api_base", None):
            # Remove /v1/completions from api_base if present
            # Strange LiteLLM behavior, but it works
            api_base = llm_config["api_base"]
            if api_base.endswith("/v1/completions"):
                api_base = api_base.replace("/v1/completions", "/v1")
                api_params["api_base"] = api_base

        # Add response_format only if explicitly provided
        if response_format:
            api_params["response_format"] = response_format

        response = await litellm.acompletion(**api_params)

        # Handle streaming response
        if llm_config.get("stream", False):
            full_content = ""
            async for chunk in response:
                content = chunk.choices[0].delta.content or ""
                full_content += content
            content = full_content

            # Construct a mock response object similar to non-streaming responses
            # Not sure if I need to use this...we'll see
            reconstructed_response = SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=full_content, role="assistant")
                    )
                ],
                _hidden_params={
                    "cache_hit": False,
                    "request_id": llm_config.get("request_id"),
                    "hidden": True,
                },
            )
            return reconstructed_response
        else:
            # Handle non-streaming response
            hidden_params = response._hidden_params
            logger.info(f"Cache Hit: {hidden_params.get('cache_hit', False)}")
            content = response.choices[0].message.content

            # Set cache_hit in _hidden_params if not already set
            if "cache_hit" not in hidden_params:
                hidden_params["cache_hit"] = False

            return response

    except litellm.BadRequestError as e:
        logger.error(f"BadRequestError: {e}")
        raise
    except Exception as e:
        logger.error(f"Error calling LLM: {e}")
        raise


# --- Task Decomposition and Synthesis Logic (Example Implementation) ---

def decompose_query_france_example(query: str) -> list[str]:
    """
    Simulates decomposition for the specific France clothing query.
    In a real system, this would involve LLM calls or more sophisticated logic.
    """
    logger.info(f"Decomposing query: '{query}'")
    if "france" in query.lower() and "wintertime" in query.lower() and "capital" in query.lower():
        return [
            "What is the capital city of France?",
            "What is the average temperature in Paris during Wintertime?", # Hardcoded Paris based on expected answer to Q1
            "What clothes should I wear when it's 30F in Wintertime?" # Hardcoded 30F based on expected answer to Q2
        ]
    else:
        logger.warning("Query does not match the specific France example format for decomposition.")
        return [] # Or handle other queries differently

def simulate_sub_question_call(sub_question: str, context: dict) -> str:
    """
    Simulates an LLM call to answer a sub-question based on the France example.
    """
    logger.info(f"Simulating LLM call for sub-question: '{sub_question}'")
    answer = f"Placeholder answer for: '{sub_question}'" # Default

    if "capital city of france" in sub_question.lower():
        answer = "Paris"
    elif "average temperature in paris" in sub_question.lower() and "wintertime" in sub_question.lower():
        answer = "Approximately 30F (around 0C)."
    elif "clothes should i wear" in sub_question.lower() and "30f" in sub_question.lower():
        answer = "You should wear warm layers, including a thick sweater, a winter coat, scarf, hat, and gloves."

    logger.info(f"-> Simulated Answer: {answer}")
    return answer

def synthesize_results_france_example(original_query: str, sub_answers: dict) -> str:
    """
    Simulates synthesizing the final answer from sub-answers for the France example.
    """
    logger.info("Synthesizing final answer from sub-answers...")
    # In a real system, this might involve another LLM call with context.
    # Here, we just format the collected answers.

    capital = sub_answers.get("What is the capital city of France?", "Unknown Capital")
    temp = sub_answers.get("What is the average temperature in Paris during Wintertime?", "Unknown Temperature")
    clothing = sub_answers.get("What clothes should I wear when it's 30F in Wintertime?", "Unknown Clothing Advice")

    synthesis = (
        f"Based on your query: '{original_query}'\n"
        f"- The capital of France is {capital}.\n"
        f"- The average temperature there in Wintertime is {temp}.\n"
        f"- Therefore, recommended clothing includes: {clothing}"
    )
    logger.info("-> Synthesized Answer:\n" + synthesis)
    return synthesis


async def handle_complex_query(query: str, config: Dict):
    """
    Orchestrates the decomposition, sub-question execution (simulated),
    and synthesis for a complex query like the France example.
    """
    logger.info(f"Handling complex query: '{query}'")

    # 1. Decompose
    sub_questions = decompose_query_france_example(query)
    if not sub_questions:
        logger.warning("Could not decompose query, attempting direct call (if implemented).")
        # Optionally, fall back to a direct litellm_call here if needed
        # return await litellm_call(config) # Example fallback
        return "Could not decompose the query using the example logic."


    # 2. Execute Sub-questions (Simulated)
    sub_answers = {}
    context = {"original_query": query} # Context can be built up sequentially

    # Execute sequentially as per the example's dependency
    for question in sub_questions:
        # Update context based on previous answers if necessary for the *next* question's simulation
        # (e.g., pass the capital to the temperature question simulation)
        # This simulation is simple and uses hardcoded values based on expected flow.
        if "average temperature" in question and "Paris" not in question:
             # If the capital was found, inject it into the question for simulation lookup
             capital = sub_answers.get("What is the capital city of France?")
             if capital:
                 question = question.replace("[Capital City]", capital) # Placeholder replacement

        if "clothes should i wear" in question and "[Temperature]" not in question:
             # If the temp was found, inject it
             temp_answer = sub_answers.get("What is the average temperature in Paris during Wintertime?")
             # Extract numeric part for simulation lookup if needed (simplistic extraction)
             import re
             match = re.search(r'(\d+F)', temp_answer)
             if match:
                 temp_str = match.group(1)
                 question = question.replace("[Temperature]", temp_str)


        answer = simulate_sub_question_call(question, context)
        sub_answers[question] = answer
        context[f"answer_to_{question[:30]}..."] = answer # Update context

    # 3. Synthesize Results (Simulated)
    final_answer = synthesize_results_france_example(query, sub_answers)

    return final_answer

# --- End of Task Decomposition Logic ---



# Usage
async def main():
    # Keep verbose off for cleaner demo output
    # litellm.set_verbose = True
    initialize_litellm_cache() # Ensure cache is ready if needed by underlying calls
    # from src.settings.config import config # Load base config if needed - Not required for this simulation test

    # --- Test the Complex Query Handler ---
    complex_query = "What clothes should I wear in Wintertime in the capital city of France?"
    # We don't need a full config for the simulation, but pass an empty dict for now
    complex_config = {}

    print(f"\n--- Testing Complex Query Handling ---")
    final_result = await handle_complex_query(complex_query, complex_config)
    print("\n--- FINAL SYNTHESIZED RESULT ---")
    print(final_result)
    print("----------------------------------\n")


    # --- Original Example (Optional - can be commented out) ---
    # print("--- Testing Original litellm_call (JSON example) ---")
    # class UserDetails(BaseModel):
    #     """A model representing user details including name, age and favorite color"""
    #     name: str = Field(description="The user's full name")
    #     age: int = Field(description="The user's age in years")
    #     favorite_color: str = Field(description="The user's preferred color")

    # updates = {
    #     "llm_config": {
    #         "api_base": "http://192.168.86.49:30002/v1/completions", # Example API base
    #         "model": "openai/neuralmagic/Meta-Llama-3.1-8B-Instruct-FP8", # Example model
    #         "messages": [
    #             {"role": "system", "content": "Return JSON."},
    #             {"role": "user", "content": "John Doe, 30, blue."},
    #         ],
    #         "response_format": UserDetails,
    #         "stream": False, # Easier to print non-streaming for this example
    #         "caching": True,
    #     }
    # }
    # merged_config = always_merger.merge(config, updates)
    # try:
    #     response = await litellm_call(merged_config)
    #     if isinstance(response, BaseModel):
    #          print("Response (Pydantic Model):", response.model_dump_json(indent=2))
    #     elif hasattr(response, 'choices'): # Handle non-streaming structure
    #          content = response.choices[0].message.content
    #          print("Response Content:", content)
    #     else:
    #          print("Response:", response) # Fallback
    #     # hidden_params = response._hidden_params
    #     # print("Hidden Params:", hidden_params)
    # except Exception as e:
    #      print(f"Error during original litellm_call test: {e}")
    # print("--------------------------------------------------\n")


if __name__ == "__main__":
    asyncio.run(main())
