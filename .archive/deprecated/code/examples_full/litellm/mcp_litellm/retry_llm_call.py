"""
Module: retry_llm_call.py
Description: Model Context Protocol (MCP) integration

External Dependencies:
- loguru: https://loguru.readthedocs.io/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

from typing import Callable, Dict, Any, List, Optional, Union, Tuple
import asyncio
from loguru import logger

async def retry_llm_call(
    llm_call: Callable,  # The LLM function to call (e.g., call_litellm_structured)
    # llm_config: QuestionItem,  # Configuration object (QuestionItem) - Replaced by individual args
    model: str,
    messages: List[Dict[str, str]], # Pass the already substituted messages
    temperature: Optional[float],
    max_tokens: Optional[int],
    api_base: Optional[str],
    response_model: Optional[Any], # Pass response_model if needed
    validation_strategies: List[Callable],  # List of validation functions
    max_retries: int = 3,  # Maximum number of retries
) -> Tuple[Dict, int]: # Return response and retry count
    """
    A generic function to handle retries, validation, and iterative improvement for LLM calls.

    Args:
        llm_call (Callable): The LLM function to call.
        llm_config (QuestionItem): Configuration object containing LLM parameters.
        validation_strategies (List[Callable]): List of functions to validate the LLM response.
        max_retries (int): Maximum number of retries.

    Returns:
        Tuple[Dict, int]: A tuple containing the validated LLM response dictionary and the number of retries taken (0-indexed).
    """
    logger.debug(f"Retry Call: Received initial messages: {messages}") # ADDED LOGGING
    retries = 0
    # Initial message list constructed once
    # Initialize messages list
    current_messages = messages # Start with the substituted messages

    while retries < max_retries:
        try:
            # Construct the nested config dict for the underlying litellm_call on each attempt

            llm_params = {
                "model": model,
                "messages": current_messages, # Use the current messages list
                "temperature": temperature,
                "max_tokens": max_tokens,
                "api_base": api_base,
                # Add other relevant parameters from QuestionItem if litellm_call uses them
                # e.g., "top_p": llm_config.top_p, "stream": llm_config.stream, etc.
            }
            # If response_model is specified, add it for structured output
            if response_model:
                 # Assuming litellm_call uses 'response_model' key within llm_config
                 # Adjust key if litellm_call expects something different (e.g., 'response_format')
                 llm_params["response_model"] = response_model

            call_config = {"llm_config": llm_params} # Create the nested structure

            logger.debug(f"Attempt {retries + 1}: Calling LLM with config: {call_config}")
            logger.debug(f"Attempt {retries + 1}: Messages being sent: {current_messages}") # ADDED LOGGING (This line might already exist from previous attempt, ensure it's correct)'
            response = await llm_call(call_config) # Pass the nested dict
            validation_errors = []

            # Apply all validation strategies
            for validate in validation_strategies:
                validation_result = validate(response)
                if validation_result is not True:
                    validation_errors.append(validation_result)

            # If all validations pass, return the response
            if not validation_errors:
                return response, retries

            # If any validation fails, log the errors and retry
            logger.warning(f"Attempt {retries + 1}: Validation failed: {', '.join(validation_errors)}")
            # Append feedback to the current_messages list for the next retry attempt
            current_messages.append({"role": "assistant", "content": str(response)}) # Add LLM's failed response'
            current_messages.append({
                "role": "user",
                "content": f"The previous response failed validation with errors: {', '.join(validation_errors)}. Please correct the response based on the original request and the validation errors.",
            })
        except Exception as e:
            logger.error(f"Attempt {retries + 1} failed: {e}")
        retries += 1

    # Max retries exceeded: Add the failure reason to the messages object
    # Max retries exceeded
    failure_message = f"Max retries ({max_retries}) exceeded. The LLM failed to generate a valid response after validation attempts."
    # Note: We don't modify the original llm_config (QuestionItem) here.
    # The failure is raised, and the calling function (engine.py) handles the error result.
    logger.error(failure_message)
    raise Exception(failure_message)


async def main():
    return


if __name__ == "__main__":
    asyncio.run(main())
