"""
Claude Code Configuration for Marker
Module: claude_config.py
Description: Configuration management and settings

Provides easy configuration of optional Claude Code features for document processing.
All features are disabled by default for performance - users opt-in to accuracy improvements.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any
from pathlib import Path
import os

from extractor.core.processors.claude_verification_system import (
    ClaudeConfig, 
    ClaudeFeature, 
    ClaudeConfigBuilder
)

@dataclass
class MarkerClaudeSettings:
    """
    Main Claude settings for Marker document processing.
    
    All Claude features are disabled by default to maintain performance.
    Users can enable specific features based on their accuracy/speed requirements.
    """
    
    # Global Claude settings
    enable_claude_features: bool = False
    claude_workspace_dir: Optional[str] = None
    claude_model: str = "claude-3-5-sonnet-20241022"
    max_concurrent_analyses: int = 2
    analysis_timeout_seconds: float = 120.0
    
    # Feature toggles
    enable_section_verification: bool = False
    enable_table_merge_analysis: bool = False
    enable_content_validation: bool = False
    enable_structure_analysis: bool = False
    
    # Performance controls
    skip_claude_if_processing_exceeds_seconds: float = 300.0
    max_claude_analyses_per_document: int = 10
    fallback_to_heuristics_on_error: bool = True
    
    # Quality thresholds
    table_merge_confidence_threshold: float = 0.75
    section_verification_confidence_threshold: float = 0.8
    section_confidence_threshold: float = 0.75  # Alias for section_verification_confidence_threshold
    content_confidence_threshold: float = 0.8  # Threshold for content validation
    structure_confidence_threshold: float = 0.85  # Threshold for structure analysis
    min_tables_for_claude_analysis: int = 2
    min_sections_for_verification: int = 3
    
    # Auto-fix settings
    auto_fix_sections: bool = False  # Automatically apply section hierarchy fixes
    
    # Cost control (Claude Code instances are resource intensive)
    max_claude_budget_per_document: Optional[float] = None  # In seconds
    warn_on_long_analysis: bool = True
    log_claude_performance: bool = True

    def to_claude_config(self) -> ClaudeConfig:
        """Convert to internal ClaudeConfig object."""
        
        workspace_dir = None
        if self.claude_workspace_dir:
            workspace_dir = Path(self.claude_workspace_dir)
        
        features = {
            ClaudeFeature.SECTION_VERIFICATION: self.enable_section_verification,
            ClaudeFeature.TABLE_MERGE_ANALYSIS: self.enable_table_merge_analysis,
            ClaudeFeature.CONTENT_VALIDATION: self.enable_content_validation,
            ClaudeFeature.STRUCTURE_ANALYSIS: self.enable_structure_analysis
        }
        
        return ClaudeConfig(
            enabled=self.enable_claude_features,
            workspace_dir=workspace_dir,
            model=self.claude_model,
            max_concurrent=self.max_concurrent_analyses,
            timeout=self.analysis_timeout_seconds,
            features=features,
            table_merge_confidence_threshold=self.table_merge_confidence_threshold,
            section_verification_confidence_threshold=self.section_verification_confidence_threshold,
            min_tables_for_analysis=self.min_tables_for_claude_analysis,
            min_sections_for_verification=self.min_sections_for_verification,
            skip_claude_if_processing_time_exceeds=self.skip_claude_if_processing_exceeds_seconds,
            max_claude_analysis_per_document=self.max_claude_analyses_per_document,
            fallback_to_heuristics=self.fallback_to_heuristics_on_error
        )

# Predefined configurations for common use cases
CLAUDE_DISABLED = MarkerClaudeSettings(
    enable_claude_features=False
)

CLAUDE_MINIMAL = MarkerClaudeSettings(
    enable_claude_features=True,
    enable_section_verification=True,
    max_concurrent_analyses=1,
    analysis_timeout_seconds=60.0
)

CLAUDE_TABLE_ANALYSIS_ONLY = MarkerClaudeSettings(
    enable_claude_features=True,
    enable_table_merge_analysis=True,
    min_tables_for_claude_analysis=2,
    table_merge_confidence_threshold=0.75
)

CLAUDE_ACCURACY_FOCUSED = MarkerClaudeSettings(
    enable_claude_features=True,
    enable_section_verification=True,
    enable_table_merge_analysis=True,
    enable_content_validation=True,
    enable_structure_analysis=True,
    max_concurrent_analyses=3,
    analysis_timeout_seconds=180.0,
    table_merge_confidence_threshold=0.8,
    section_verification_confidence_threshold=0.85
)

CLAUDE_RESEARCH_QUALITY = MarkerClaudeSettings(
    enable_claude_features=True,
    enable_section_verification=True,
    enable_table_merge_analysis=True,
    enable_content_validation=True,
    max_concurrent_analyses=4,
    analysis_timeout_seconds=300.0,
    table_merge_confidence_threshold=0.85,
    section_verification_confidence_threshold=0.9,
    skip_claude_if_processing_exceeds_seconds=600.0  # 10 minutes
)

def get_claude_config_from_env() -> MarkerClaudeSettings:
    """
    Load Claude configuration from environment variables.
    
    Environment variables:
    - MARKER_CLAUDE_ENABLED: Enable Claude features (default: false)
    - MARKER_CLAUDE_SECTION_VERIFICATION: Enable section verification 
    - MARKER_CLAUDE_TABLE_ANALYSIS: Enable table merge analysis
    - MARKER_CLAUDE_WORKSPACE: Claude workspace directory
    - MARKER_CLAUDE_MODEL: Claude model to use
    - MARKER_CLAUDE_TIMEOUT: Analysis timeout in seconds
    - MARKER_CLAUDE_CONFIDENCE_THRESHOLD: Confidence threshold (0.0-1.0)
    """
    
    def env_bool(key: str, default: bool = False) -> bool:
        return os.getenv(key, str(default)).lower() in ('true', '1', 'yes', 'on')
    
    def env_float(key: str, default: float) -> float:
        try:
            return float(os.getenv(key, str(default)))
        except ValueError:
            return default
    
    def env_int(key: str, default: int) -> int:
        try:
            return int(os.getenv(key, str(default)))
        except ValueError:
            return default
    
    return MarkerClaudeSettings(
        enable_claude_features=env_bool('MARKER_CLAUDE_ENABLED', False),
        enable_section_verification=env_bool('MARKER_CLAUDE_SECTION_VERIFICATION', False),
        enable_table_merge_analysis=env_bool('MARKER_CLAUDE_TABLE_ANALYSIS', False),
        enable_content_validation=env_bool('MARKER_CLAUDE_CONTENT_VALIDATION', False),
        enable_structure_analysis=env_bool('MARKER_CLAUDE_STRUCTURE_ANALYSIS', False),
        
        claude_workspace_dir=os.getenv('MARKER_CLAUDE_WORKSPACE'),
        claude_model=os.getenv('MARKER_CLAUDE_MODEL', 'claude-3-5-sonnet-20241022'),
        analysis_timeout_seconds=env_float('MARKER_CLAUDE_TIMEOUT', 120.0),
        max_concurrent_analyses=env_int('MARKER_CLAUDE_CONCURRENT', 2),
        
        table_merge_confidence_threshold=env_float('MARKER_CLAUDE_TABLE_CONFIDENCE', 0.75),
        section_verification_confidence_threshold=env_float('MARKER_CLAUDE_SECTION_CONFIDENCE', 0.8),
        
        skip_claude_if_processing_exceeds_seconds=env_float('MARKER_CLAUDE_SKIP_TIMEOUT', 300.0),
        fallback_to_heuristics_on_error=env_bool('MARKER_CLAUDE_FALLBACK', True),
        log_claude_performance=env_bool('MARKER_CLAUDE_LOG_PERFORMANCE', True)
    )

def get_recommended_config_for_use_case(use_case: str) -> MarkerClaudeSettings:
    """
    Get recommended Claude configuration for specific use cases.
    
    Args:
        use_case: One of 'production', 'research', 'accuracy', 'tables_only', 'disabled'
    """
    
    configs = {
        'disabled': CLAUDE_DISABLED,
        'minimal': CLAUDE_MINIMAL,
        'production': CLAUDE_MINIMAL,
        'tables_only': CLAUDE_TABLE_ANALYSIS_ONLY,
        'table_analysis_only': CLAUDE_TABLE_ANALYSIS_ONLY,
        'accuracy': CLAUDE_ACCURACY_FOCUSED,
        'research': CLAUDE_RESEARCH_QUALITY
    }
    
    return configs.get(use_case, CLAUDE_DISABLED)

def validate_claude_config(settings: MarkerClaudeSettings) -> Dict[str, Any]:
    """
    Validate Claude configuration and provide recommendations.
    
    Returns validation results and warnings.
    """
    
    validation = {
        "valid": True,
        "warnings": [],
        "recommendations": [],
        "estimated_slowdown": "none"
    }
    
    if not settings.enable_claude_features:
        validation["estimated_slowdown"] = "none"
        return validation
    
    # Check for potential performance issues
    enabled_features = [
        settings.enable_section_verification,
        settings.enable_table_merge_analysis,
        settings.enable_content_validation,
        settings.enable_structure_analysis
    ]
    
    feature_count = sum(enabled_features)
    
    if feature_count == 0:
        validation["warnings"].append("Claude enabled but no features selected")
        validation["recommendations"].append("Enable at least one Claude feature or disable Claude")
    
    if feature_count >= 3:
        validation["warnings"].append("Multiple Claude features enabled - significant slowdown expected")
        validation["estimated_slowdown"] = "high"
    elif feature_count >= 2:
        validation["estimated_slowdown"] = "medium"
    else:
        validation["estimated_slowdown"] = "low"
    
    # Check timeout settings
    if settings.analysis_timeout_seconds > 300:
        validation["warnings"].append("Very long analysis timeout - documents may take a long time to process")
    
    if settings.max_concurrent_analyses > 4:
        validation["warnings"].append("High concurrency may overwhelm Claude Code instances")
    
    # Check confidence thresholds
    if settings.table_merge_confidence_threshold < 0.7:
        validation["warnings"].append("Low table merge confidence threshold may cause incorrect merges")
    
    if settings.section_verification_confidence_threshold < 0.75:
        validation["warnings"].append("Low section verification threshold may apply incorrect corrections")
    
    # Recommendations
    if feature_count >= 2:
        validation["recommendations"].append("Consider using CLAUDE_TABLE_ANALYSIS_ONLY for better performance")
    
    if settings.skip_claude_if_processing_exceeds_seconds < 180:
        validation["recommendations"].append("Consider increasing skip timeout for complex documents")
    
    return validation

# CLI integration helpers
def print_claude_config_help():
    """Print help information about Claude configuration options."""
    
    help_text = """
Claude Code Features for Marker

Claude Code instances can significantly improve extraction accuracy but are slower.
All features are DISABLED by default for performance.

Available Features:
  section_verification    - Verify section hierarchy and titles using Claude
  table_merge_analysis   - Intelligent table merging based on content analysis  
  content_validation     - Validate overall document structure
  structure_analysis     - Analyze document organization

Predefined Configurations:
  disabled        - No Claude features (default, fastest)
  minimal         - Only section verification (balanced)
  tables_only     - Only table merge analysis
  accuracy        - Most features enabled (slower, higher quality)
  research        - All features, high thresholds (slowest, highest quality)

Environment Variables:
  MARKER_CLAUDE_ENABLED=true/false
  MARKER_CLAUDE_SECTION_VERIFICATION=true/false
  MARKER_CLAUDE_TABLE_ANALYSIS=true/false
  MARKER_CLAUDE_WORKSPACE=/path/to/workspace
  MARKER_CLAUDE_TIMEOUT=120
  MARKER_CLAUDE_CONFIDENCE_THRESHOLD=0.75

Performance Impact:
  - Section verification: +30-60s per document
  - Table analysis: +15-30s per table pair
  - Multiple features: Can double or triple processing time
  - Benefits: Significantly improved accuracy for complex documents

Example Usage:
  # Production (fast)
  marker --claude-config production document.pdf
  
  # Research quality (slow but accurate)  
  marker --claude-config research document.pdf
  
  # Only improve table merging
  marker --claude-config tables_only document.pdf
"""
    
    print(help_text)

def create_claude_config_for_cli(config_name: str, **overrides) -> MarkerClaudeSettings:
    """
    Create Claude configuration for CLI usage.
    
    Args:
        config_name: Predefined config name or 'custom'
        **overrides: Override specific settings
    """
    
    if config_name == 'custom':
        base_config = get_claude_config_from_env()
    else:
        base_config = get_recommended_config_for_use_case(config_name)
    
    # Apply overrides
    for key, value in overrides.items():
        if hasattr(base_config, key):
            setattr(base_config, key, value)
    
    return base_config

# Integration example for enhanced_table.py
def integrate_claude_with_enhanced_processor(enhanced_processor, claude_config_name: str = "disabled"):
    """
    Integrate Claude features with enhanced table processor.
    
    Args:
        enhanced_processor: Instance of EnhancedTableProcessor
        claude_config_name: Configuration preset name
    """
    
    claude_settings = get_recommended_config_for_use_case(claude_config_name)
    claude_config = claude_settings.to_claude_config()
    
    # Import and integrate
    from extractor.core.processors.claude_verification_system import ClaudeDocumentProcessor, integrate_claude_features
    
    # Add Claude processor to enhanced processor
    integrate_claude_features(enhanced_processor, claude_config)
    
    # Log configuration
    if claude_settings.log_claude_performance:
        from loguru import logger
        enabled_features = [name for name, enabled in {
            'section_verification': claude_settings.enable_section_verification,
            'table_analysis': claude_settings.enable_table_merge_analysis,
            'content_validation': claude_settings.enable_content_validation,
            'structure_analysis': claude_settings.enable_structure_analysis
        }.items() if enabled]
        
        if enabled_features:
            logger.info(f"Claude features enabled: {', '.join(enabled_features)}")
            logger.info(f"Expected slowdown: {validate_claude_config(claude_settings)['estimated_slowdown']}")
        else:
            logger.info("Claude features disabled - using heuristic processing only")

if __name__ == "__main__":
    # Demo configuration options
    print("=== Claude Configuration Options ===")
    
    configs = [
        ("Disabled (Default)", CLAUDE_DISABLED),
        ("Minimal (Production)", CLAUDE_MINIMAL), 
        ("Table Analysis Only", CLAUDE_TABLE_ANALYSIS_ONLY),
        ("Accuracy Focused", CLAUDE_ACCURACY_FOCUSED),
        ("Research Quality", CLAUDE_RESEARCH_QUALITY)
    ]
    
    for name, config in configs:
        validation = validate_claude_config(config)
        print(f"\n{name}:")
        print(f"  Enabled: {config.enable_claude_features}")
        if config.enable_claude_features:
            enabled_features = []
            if config.enable_section_verification:
                enabled_features.append("sections")
            if config.enable_table_merge_analysis:
                enabled_features.append("tables")
            if config.enable_content_validation:
                enabled_features.append("content")
            if config.enable_structure_analysis:
                enabled_features.append("structure")
            print(f"  Features: {', '.join(enabled_features) if enabled_features else 'none'}")
            print(f"  Timeout: {config.analysis_timeout_seconds}s")
            print(f"  Estimated slowdown: {validation['estimated_slowdown']}")
    
    print("\n=== Environment Configuration ===")
    env_config = get_claude_config_from_env()
    print(f"Claude enabled from env: {env_config.enable_claude_features}")
    
    print("\n=== Validation Example ===")
    validation = validate_claude_config(CLAUDE_ACCURACY_FOCUSED)
    print(f"Configuration valid: {validation['valid']}")
    print(f"Warnings: {validation['warnings']}")
    print(f"Recommendations: {validation['recommendations']}")