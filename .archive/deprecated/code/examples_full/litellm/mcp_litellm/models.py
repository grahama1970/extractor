"""
Module: models.py
Description: Data models and schema definitions

External Dependencies:
- pydantic: https://docs.pydantic.dev/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

# -*- coding: utf-8 -*-
"""
Description:
    Defines Pydantic models for the MCP LiteLLM service request and response structures.
    These models ensure data validation and structure for interactions with the service.

Core Lib Links:
    - Pydantic Documentation: https://docs.pydantic.dev/latest/

Sample I/O:
    N/A (This file defines models, not executable logic)
"""

from typing import List, Optional, Any, Literal
from pydantic import BaseModel, Field

# ============================================================================ #
#                                Request Models                                #
# ============================================================================ #

class TaskItem(BaseModel):
    """
    Represents a single task in the batch, with dependencies.
    """
    task_id: str = Field(..., description="Unique identifier for this task.")
    dependencies: List[str] = Field(default_factory=list, description="List of task_ids this task depends on.")
    question: str = Field(..., description="The text of the question to be processed by the LLM.")
    model: Optional[str] = Field(
        default='openai/gpt-4o-mini',
        description="The LiteLLM model string to use for this task."
    )
    validation_strategy: Optional[str] = Field(
        default='pydantic',
        description="Strategy for validating the LLM response (e.g., 'pydantic')."
    )
    temperature: Optional[float] = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for the LLM."
    )
    max_tokens: Optional[int] = Field(
        default=1000,
        gt=0,
        description="Maximum number of tokens to generate in the response."
    )
    api_base: Optional[str] = Field(
        default=None,
        description="Optional API base URL for the LLM provider."
    )
    response_model: Optional[str] = Field(
        default=None,
        description="Optional Pydantic model name (as string) for structured response parsing."
    )
    # Additional LiteLLM parameters can be added here as needed


class BatchRequest(BaseModel):
    """
    Represents a batch request containing multiple task items.
    """
    tasks: List[TaskItem] = Field(..., description="A list of tasks to be processed with dependencies.")

# ============================================================================ #
#                                Response Models                               #
# ============================================================================ #

class ResultItem(BaseModel):
    """
    Represents the result for a single task item from a batch request.
    """
    task_id: str = Field(..., description="Identifier linking back to the original TaskItem task_id.")
    status: Literal['success', 'error', 'dependency_failed'] = Field(
        ...,
        description="Indicates if the processing was successful, resulted in an error, or failed due to dependency failure."
    )
    result: Optional[Any] = Field(
        default=None,
        description="The processed result from the LLM (can be structured or raw text)."
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Detailed error message if the status is 'error' or 'dependency_failed'."
    )
    confidence: Optional[float] = Field(
        default=None,
        description="Confidence score associated with the result, if applicable."
    )
    retry_count: Optional[int] = Field(
        default=0,
        ge=0,
        description="Number of retries attempted for this task."
    )


class BatchResponse(BaseModel):
    """
    Represents the batch response containing results for all processed tasks.
    """
    responses: List[ResultItem] = Field(..., description="A list of responses corresponding to the input tasks.")


# ============================================================================ #
#                             Lessons Learned Models                           #
# ============================================================================ #

class LessonQueryRequest(BaseModel):
    """
    Request model for querying lessons learned.
    """
    query_text: str = Field(..., description="The natural language query to search for relevant lessons.")
    top_k: int = Field(default=3, gt=0, description="The maximum number of lessons to return.")


class LessonResultItem(BaseModel):
    """
    Represents a single lesson learned document returned by the query.
    Includes the document content and similarity score.
    """
    id: str = Field(..., description="The unique identifier (_id) of the lesson document in ArangoDB.")
    key: str = Field(..., description="The unique key (_key) of the lesson document in ArangoDB.")
    score: float = Field(..., description="The similarity score between the query and the lesson.")
    lesson: dict = Field(..., description="The full lesson learned document content.")


class LessonQueryResponse(BaseModel):
    """
    Response model for the lessons learned query endpoint.
    Contains a list of relevant lesson documents.
    """
    lessons: List[LessonResultItem] = Field(..., description="A list of relevant lessons learned, sorted by similarity.")


# ============================================================================ #
#                                End of File                                   #
# ============================================================================ #
