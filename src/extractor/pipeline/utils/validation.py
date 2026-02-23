"""
Stage boundary validation utilities for the extractor pipeline.

This module provides centralized validation for pipeline artifacts to ensure
consistent schemas and fail-fast behavior.
"""

import json
from typing import Dict, Any, Optional, Tuple, Type
from pydantic import BaseModel, ValidationError
from functools import wraps

from extractor.pipeline.schemas.reflow import ReflowOutput, validate_reflow_output
from extractor.pipeline.schemas.summarizer import SummaryOutput, validate_summary_output


def validate_json_file(filepath: str, schema: BaseModel) -> Tuple[bool, Optional[str]]:
    """Validate a JSON file against a Pydantic schema."""
    try:
        with open(filepath, "r") as f:
            data = json.load(f)

        # Use schema-specific validation functions if available
        if schema == ReflowOutput:
            result = validate_reflow_output(data)
            return result if isinstance(result, tuple) else (result, None)
        elif schema == SummaryOutput:
            result = validate_summary_output(data)
            return result if isinstance(result, tuple) else (result, None)

        # Generic validation
        schema.model_validate(data)
        return True, None
    except ValidationError as e:
        return False, str(e)
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"
    except FileNotFoundError:
        return False, f"File not found: {filepath}"


def validate_stage_output(
    stage_name: str, output_data: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """Validate output from a specific pipeline stage."""
    # Map stage names to their expected schemas
    stage_schemas = {
        "stage07": (ReflowOutput, validate_reflow_output),
        "stage09": (SummaryOutput, validate_summary_output),
        # Add more stages as their schemas are integrated
    }

    if stage_name not in stage_schemas:
        # No schema defined for this stage yet
        return True, None

    schema, validator = stage_schemas[stage_name]

    try:
        result = validator(output_data)
        # Handle different return types from validators
        if isinstance(result, tuple):
            return result
        else:
            return result, None
    except Exception as e:
        return False, f"Validation error: {str(e)}"


def with_stage_validation(
    stage_name: str, validate_input: bool = True, validate_output: bool = True
):
    """Decorator to add validation to stage functions."""

    def decorator(stage_func):
        @wraps(stage_func)
        def wrapper(input_data: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
            # Input validation
            if validate_input and input_data:
                # TODO: Implement input validation per stage
                pass

            # Run the stage
            output_data = stage_func(input_data, *args, **kwargs)

            # Output validation
            if validate_output and output_data:
                is_valid, error = validate_stage_output(stage_name, output_data)
                if not is_valid:
                    raise ValueError(f"Stage {stage_name} output validation failed: {error}")

            return output_data

        return wrapper

    return decorator


def get_stage_input_schema(stage_num: int) -> Optional[BaseModel]:
    """Get the expected input schema for a given stage number."""
    # Define input schemas based on pipeline flow
    stage_inputs = {
        # Stage 03 expects sections from Stage 02
        3: None,  # TODO: Define SectionInput schema
        # Stage 04 expects verified blocks from Stage 03
        4: None,  # TODO: Define VerifiedBlocksInput schema
        # Stage 05 expects sections from Stage 04
        5: None,  # TODO: Define SectionInput schema
        # Stage 07 expects tables from Stage 05
        7: None,  # TODO: Define TableInput schema
        # Stage 09 expects reflowed sections from Stage 07
        9: None,  # TODO: Define ReflowedInput schema
    }
    return stage_inputs.get(stage_num)


class StageInputSchema:
    """Base class for stage input validation."""

    @classmethod
    def validate_file(cls, filepath: str) -> Tuple[bool, Optional[str]]:
        """Validate an input file for this stage."""
        return validate_json_file(filepath, cls)

    @classmethod
    def validate_data(cls, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate input data for this stage."""
        try:
            cls.model_validate(data)
            return True, None
        except ValidationError as e:
            return False, str(e)


def create_stage_validator(
    stage_num: int,
    input_schema: Optional[Type[BaseModel]] = None,
    output_schema: Optional[Type[BaseModel]] = None,
):
    """Factory function to create validators for specific stages."""

    def validator_wrapper(stage_func):
        @wraps(stage_func)
        def validated_function(*args, **kwargs):
            # Input validation
            if input_schema and args:
                input_data = args[0] if isinstance(args[0], dict) else None
                if input_data:
                    is_valid, error = validate_data_with_schema(input_data, input_schema)
                    if not is_valid:
                        raise ValueError(f"Invalid input for stage {stage_num}: {error}")

            # Execute stage
            result = stage_func(*args, **kwargs)

            # Output validation
            if output_schema and isinstance(result, dict):
                is_valid, error = validate_data_with_schema(result, output_schema)
                if not is_valid:
                    raise ValueError(f"Invalid output from stage {stage_num}: {error}")

            return result

        return validated_function

    return validator_wrapper


def validate_data_with_schema(
    data: Dict[str, Any], schema: Type[BaseModel]
) -> Tuple[bool, Optional[str]]:
    """Generic validation helper."""
    try:
        schema.model_validate(data)
        return True, None
    except ValidationError as e:
        return False, str(e)
