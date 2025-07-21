"""
Module: usage_llm_retry.py
Description: Large Language Model integration and management

External Dependencies:
- pydantic: https://docs.pydantic.dev/
- loguru: https://loguru.readthedocs.io/
- litellm: https://docs.litellm.ai/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

import asyncio
from typing import Dict, List, Literal
from pydantic import BaseModel, Field
from loguru import logger

# Import the shared functions
from src.generate_schema_for_llm.shared.validation_strategies import (
    validate_description_length,
    validate_description_present,
    validate_field_type,
    VALIDATION_STRATEGIES,
)
from src.generate_schema_for_llm.shared.retry_llm_call import retry_llm_call
from src.generate_schema_for_llm.shared.call_litellm_structured import call_litellm_structured

# Define a Pydantic model for the LLM response
class CollectionDescription(BaseModel):
    name: str = Field(..., description="Name of the collection.")
    description: str = Field(..., description="Description of the collection.")
    type: Literal["document", "edge"] = Field(..., description="Type of the collection (document or edge).")

# Example LLM call with validation
async def describe_collection(
    collection_name: str, 
    sample_rows: List[Dict], 
    llm_config: Dict,
    max_retries: int = 3,
) -> Dict:
    """
    Describe a collection using the LLM with retry logic and validation.
    """
    system_message = (
        "You are a DBA expert that concisely explains the purpose and structure of ArangoDB collections. "
        "Always output in well-formatted JSON with no additional text."
    )
    user_message = (
        f"Describe the purpose of the collection '{collection_name}' in 1-2 sentences, focusing on its primary function and the type of data it stores. "
        f"Use the following sample rows as context:\n"
        f"{sample_rows}\n\n"
        "Do not include technical details or field names. Keep the description concise and clear."
    )
    messages = [{"role": "system", "content": system_message}, {"role": "user", "content": user_message}]
    llm_config["messages"] = messages
    llm_config["response_format"] = CollectionDescription

    # Use retry_llm_call to handle retries and validation
    result = await retry_llm_call(
        llm_call=call_litellm_structured,
        llm_config=llm_config,
        validation_strategies=VALIDATION_STRATEGIES,
        max_retries=max_retries,
    )
    
    if result is None:
        raise ValueError("Failed to generate valid response after retries")
        
    return result

# Main function to run the example
async def main():
    # Example configuration
    config = {
        "llm_config": {
            "model": "openai/gpt-4o-mini",  # Use your preferred model
            "temperature": 0.3,
            "messages": [],  # Initialize the messages object
            "cache": False,
        }
    }

    # Example data
    collection_name = "microsoft_products"
    sample_rows = [{"name": "Product A", "category": "Software"}]

    try:
        # Call the describe_collection function
        result = await describe_collection(
            collection_name=collection_name,
            sample_rows=sample_rows,
            llm_config=config["llm_config"],
            max_retries=3,
        )
        print("LLM response:", result)
    except Exception as e:
        print("Failed to generate a valid response:", e)
        print("Messages object:", config["llm_config"]["messages"])

# Run the example
if __name__ == "__main__":
    asyncio.run(main())