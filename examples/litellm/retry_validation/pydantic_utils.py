"""
Module: pydantic_utils.py
Description: Utility functions and helper methods

External Dependencies:
- pydantic: https://docs.pydantic.dev/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

from pydantic import BaseModel, Field
from typing import Type, List, Optional, Literal, get_origin, get_args
from enum import Enum
import json

def pydantic_to_json_schema_old(pydantic_model: Type[BaseModel]) -> str:
    """
    Converts a Pydantic model into a JSON schema.

    Args:
        pydantic_model (Type[BaseModel]): The Pydantic model to convert.

    Returns:
        str: A JSON schema string representing the Pydantic model.
    """
    schema = pydantic_model.schema()
    return json.dumps(schema, indent=2)

def pydantic_to_json_schema(pydantic_model: Type[BaseModel]) -> str:
    schema = pydantic_model.schema()

    properties = schema["properties"]

    # Generate a description of each field
    field_descriptions = []
    for field_name, field_info in properties.items():
        description = field_info.get("description", "")
        field_type = field_info.get("type", "")

        # Handle minimum and maximum values
        if "minimum" in field_info:
            description += f" (min: {field_info['minimum']})"
        if "maximum" in field_info:
            description += f" (max: {field_info['maximum']})"

        # Handle enums and literals
        if "enum" in field_info:
            enum_values = field_info["enum"]
            description += f" (allowed values: {', '.join(map(str, enum_values))})"

        # Handle lists
        # if field_type == "array":
        #     item_type = field_info.get("items", {}).get("type", "unknown")
        #     description += f" (list of {item_type})"

        # Handle optional fields
        # if field_name in schema.get("required", []):
        #     description += " (required)"
        # else:
        #     description += " (optional)"

        field_descriptions.append(f"{field_name}: {description}")
    
    # Convert list of field descriptions into a single dictionary
    json_schema = {}
    for desc in field_descriptions:
        field_name, description = desc.split(": ", 1)
        json_schema[field_name] = description
    
    return json.dumps(json_schema, indent=2)



def generate_prompt_from_schema(pydantic_model: Type[BaseModel]) -> str:
    """
    Generates a prompt that instructs the model to return responses in the specified JSON format.

    Args:
        pydantic_model (Type[BaseModel]): The Pydantic model to generate the prompt for.

    Returns:
        str: A prompt string that instructs the model to return responses in the specified format.
    """
    schema = pydantic_model.schema()
    properties = schema["properties"]

    # Generate a description of each field
    field_descriptions = []
    for field_name, field_info in properties.items():
        description = field_info.get("description", "")
        field_type = field_info.get("type", "")

        # Handle minimum and maximum values
        if "minimum" in field_info:
            description += f" (minimum: {field_info['minimum']})"
        if "maximum" in field_info:
            description += f" (maximum: {field_info['maximum']})"

        # Handle enums and literals
        if "enum" in field_info:
            enum_values = field_info["enum"]
            description += f" (allowed values: {', '.join(map(str, enum_values))})"

        # Handle lists
        if field_type == "array":
            item_type = field_info.get("items", {}).get("type", "unknown")
            description += f" (list of {item_type})"

        # Handle optional fields
        if field_name in schema.get("required", []):
            description += " (required)"
        else:
            description += " (optional)"

        field_descriptions.append(f"{field_name}: {description}")

    # Combine the descriptions into a prompt
    prompt = (
        "You are a helpful assistant that always responds in JSON format.\n"
        "Return the following information in JSON format:\n"
        + "\n".join(field_descriptions) +
        "\n\nResponse:"
    )
    return prompt

###
# Main function
###
def pydantic_to_json_schema(pydantic_model: Type[BaseModel]) -> str:
    """
    Converts a Pydantic model into a JSON schema with enhanced descriptions for fields.

    Args:
        pydantic_model (Type[BaseModel]): The Pydantic model to convert.

    Returns:
        str: A JSON schema string with enhanced field descriptions.
    """
    schema = pydantic_model.model_json_schema()
    properties = schema["properties"]

    # Generate a description of each field
    field_descriptions = {}
    for field_name, field_info in properties.items():
        description = field_info.get("description", "")
        field_type = field_info.get("type", "")

        # Handle minimum and maximum values as a range
        if "minimum" in field_info and "maximum" in field_info:
            description += f" (range: {field_info['minimum']} to {field_info['maximum']})"
        elif "minimum" in field_info:
            description += f" (min: {field_info['minimum']})"
        elif "maximum" in field_info:
            description += f" (max: {field_info['maximum']})"

        # Handle enums and literals
        if "enum" in field_info:
            enum_values = field_info["enum"]
            description += f" (allowed values: {enum_values})"

        # Handle lists
        if field_type == "array":
            item_type = field_info.get("items", {}).get("type", "unknown")
            description += f" (list of {item_type})"

        # Handle optional fields
        # if field_name in schema.get("required", []):
        #     description += " (required)"
        # else:
        #     description += " (optional)"

        field_descriptions[field_name] = description

    # Convert the dictionary of field descriptions into a JSON schema
    return json.dumps(field_descriptions, indent=2)




# Example usage
if __name__ == "__main__":
    class UserDetails(BaseModel):
        """A model representing user details including name, age, favorite color, and hobbies."""
        name: str = Field(description="The user's full name")
        age: int = Field(ge=1, le=120, description="The user's age in years")
        favorite_color: str = Field(description="The user's preferred color")
        hobbies: List[str] = Field(description="The user's hobbies")
        status: Literal["active", "inactive"] = Field(description="The user's status")
        favorite_fruit: Optional[str] = Field(description="The user's favorite fruit (optional)")

    json_schema = pydantic_to_json_schema(UserDetails)
    print(json_schema)

