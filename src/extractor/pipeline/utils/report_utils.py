"""
Shared utility functions for generating verification reports

These are used across all pipeline stages to verify outputs.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
from loguru import logger


def generate_verification_report(
    request: Dict[str, Any],
    response: Dict[str, Any],
    assertions: Dict[str, bool],
    gold_standard: Dict[str, Any],
    raw_responses: Dict[str, Any] = None,
    function_name: str = "unknown",
    stage_name: str = "unknown"
) -> Path:
    """Generate verification report for any pipeline stage.
    
    Args:
        request: The input request data
        response: The output response data
        assertions: Dict of test assertions and their results
        gold_standard: Expected capabilities/features
        raw_responses: Optional raw responses for debugging
        function_name: Name of the function being tested
        stage_name: Name of the pipeline stage (01, 02, etc.)
        
    Returns:
        Path to the generated report file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    reports_dir = Path(os.getenv("REPORTS_DIR", "reports"))
    report_path = reports_dir / f"{stage_name}_report_{timestamp}.json"
    report_path.parent.mkdir(exist_ok=True)
    
    report = {
        "timestamp": timestamp,
        "stage": stage_name,
        "function": function_name,
        "request": request,
        "response": response,
        "raw_responses": raw_responses or {},
        "gold_standard": gold_standard,
        "assertions": assertions,
        "verification": {
            "all_passed": all(assertions.values()),
            "failed": [k for k, v in assertions.items() if not v]
        }
    }
    
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"Report: {report_path}")
    return report_path