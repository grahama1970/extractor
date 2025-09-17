#!/usr/bin/env python3
"""
Configuration management for the PDF extraction pipeline.

Centralizes all configuration settings with environment variable support.
"""

from pydantic import BaseSettings, Field, validator
from pathlib import Path
from typing import List, Optional
import os


class ExtractionConfig(BaseSettings):
    """Main configuration for PDF extraction pipeline."""

    # Paths
    base_dir: Path = Field(default_factory=Path.cwd, description="Base directory for operations")
    output_dir: Path = Field(
        default=Path("/tmp"), description="Output directory for temporary files"
    )

    # Security settings
    allowed_dirs: List[Path] = Field(
        default=[
            Path("/home/graham/workspace/experiments/extractor/proof_of_concept"),
            Path("/home/graham/workspace/experiments/extractor/tmp"),
            Path("/tmp"),
        ],
        description="Directories allowed for PDF processing",
    )

    # Resource limits
    max_file_size_mb: int = Field(
        default=100, ge=1, le=1000, description="Maximum PDF file size in MB"
    )
    max_pages: int = Field(
        default=1000, ge=1, le=10000, description="Maximum number of pages to process"
    )
    max_annotations: int = Field(
        default=10000, ge=1, le=100000, description="Maximum annotations per PDF"
    )
    processing_timeout_sec: int = Field(
        default=300, ge=10, le=3600, description="Processing timeout in seconds"
    )
    max_embedding_batch: int = Field(
        default=100, ge=1, le=1000, description="Maximum batch size for embeddings"
    )

    # Performance settings
    parallel_workers: int = Field(default=4, ge=1, le=16, description="Number of parallel workers")
    batch_size: int = Field(
        default=10, ge=1, le=100, description="Default batch size for processing"
    )

    # Extraction thresholds
    header_max_length: int = Field(
        default=15, ge=5, le=50, description="Maximum header length in words"
    )
    context_distance_mm: float = Field(
        default=100.0, ge=10.0, le=500.0, description="Context distance in mm"
    )
    page_break_threshold: float = Field(
        default=0.85, ge=0.0, le=1.0, description="Page break confidence threshold"
    )
    low_confidence_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Low confidence threshold"
    )

    # Database settings
    arango_url: str = Field(default="http://localhost:8529", description="ArangoDB URL")
    arango_db: str = Field(default="pdf_annotations", description="ArangoDB database name")
    arango_username: Optional[str] = Field(default=None, description="ArangoDB username")
    arango_password: Optional[str] = Field(default=None, description="ArangoDB password")

    # Redis settings
    redis_url: str = Field(default="redis://localhost:6379", description="Redis URL")
    redis_max_connections: int = Field(
        default=50, ge=10, le=1000, description="Redis connection pool size"
    )

    # LLM settings
    enable_llm_processing: bool = Field(default=True, description="Enable LLM-based processing")
    llm_provider: str = Field(default="litellm", description="LLM provider to use")
    llm_model: str = Field(default="gpt-4o", description="Default LLM model")
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="LLM temperature")
    llm_max_tokens: int = Field(
        default=4096, ge=100, le=32000, description="Maximum tokens for LLM"
    )

    # Logging settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Logging format (json or text)")

    # Feature flags
    enable_semantic_search: bool = Field(default=True, description="Enable semantic search")
    enable_visual_validation: bool = Field(default=True, description="Enable visual validation")
    enable_cache: bool = Field(default=True, description="Enable caching")

    class Config:
        env_prefix = "PDF_EXTRACT_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @validator("allowed_dirs", pre=True)
    def parse_allowed_dirs(cls, v):
        """Parse allowed directories from environment variable."""
        if isinstance(v, str):
            # Handle comma-separated paths
            return [Path(p.strip()) for p in v.split(",")]
        return v

    @validator("base_dir", "output_dir", pre=True)
    def resolve_paths(cls, v):
        """Resolve paths to absolute."""
        if isinstance(v, str):
            return Path(v).resolve()
        return v.resolve() if isinstance(v, Path) else v

    def get_allowed_search_fields(self) -> List[str]:
        """Get allowed fields for database searches."""
        return ["content", "original_snippet", "combined_text", "type", "page"]

    def is_path_allowed(self, path: Path) -> bool:
        """Check if a path is within allowed directories."""
        resolved = path.resolve()
        for allowed_dir in self.allowed_dirs:
            try:
                allowed_resolved = allowed_dir.resolve()
                if resolved.is_relative_to(allowed_resolved):
                    return True
            except (ValueError, OSError):
                continue
        return False


# Global config instance
_config: Optional[ExtractionConfig] = None


def get_config() -> ExtractionConfig:
    """Get or create the global configuration instance."""
    global _config
    if _config is None:
        _config = ExtractionConfig()
    return _config


def reload_config() -> ExtractionConfig:
    """Reload configuration from environment."""
    global _config
    _config = ExtractionConfig()
    return _config
