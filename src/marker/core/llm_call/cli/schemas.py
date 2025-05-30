"""Pydantic schemas for CLI input/output validation."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from marker.core.llm_call.core.base import ValidationStrategy
from marker.core.llm_call.core.retry import RetryConfig


class ValidationRequest(BaseModel):
    """Request model for validation operations."""
    
    prompt: str = Field(..., description="The prompt to validate")
    model: str = Field(default="vertex_ai/gemini-2.5-flash-preview-04-17", description="LLM model to use")
    strategies: List[ValidationStrategy] = Field(default_factory=list, description="Validation strategies to apply")
    config: RetryConfig = Field(default_factory=RetryConfig, description="Retry configuration")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context for validation")
    
    class Config:
        arbitrary_types_allowed = True


class ValidationResponse(BaseModel):
    """Response model for validation operations."""
    
    success: bool = Field(..., description="Whether validation succeeded")
    result: Any = Field(None, description="The validated result")
    attempts: int = Field(..., description="Number of attempts made")
    errors: List[str] = Field(default_factory=list, description="Errors encountered during validation")
    debug_info: Optional[Dict[str, Any]] = Field(None, description="Debug information if enabled")


class ValidatorInfo(BaseModel):
    """Information about a validator."""
    
    name: str = Field(..., description="Validator name")
    module: str = Field(..., description="Module path")
    class_name: str = Field(..., description="Class name")
    description: str = Field(default="", description="Validator description")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Validator parameters")


class TraceInfo(BaseModel):
    """Debug trace information."""
    
    strategy_name: str = Field(..., description="Strategy name")
    start_time: str = Field(..., description="Start time ISO format")
    end_time: Optional[str] = Field(None, description="End time ISO format")
    duration_ms: Optional[float] = Field(None, description="Duration in milliseconds")
    result: Dict[str, Any] = Field(default_factory=dict, description="Validation result")
    context: Dict[str, Any] = Field(default_factory=dict, description="Validation context")
    children: List["TraceInfo"] = Field(default_factory=list, description="Child traces")


class DebugReport(BaseModel):
    """Debug report containing traces."""
    
    timestamp: str = Field(..., description="Report timestamp")
    traces: List[TraceInfo] = Field(default_factory=list, description="Validation traces")
    summary: Dict[str, Any] = Field(default_factory=dict, description="Summary statistics")


# Update forward references
TraceInfo.model_rebuild()