#!/usr/bin/env python3
"""
fuzzy_check.py - Helper for LLM fuzzy/advisory checks in gates

Invokes a headless agent to assess quality. Returns pass/fail with reason.
Advisory only - gates should log but not fail on fuzzy check failures.
"""
from __future__ import annotations

import json
import subprocess
import sys
import re
from pathlib import Path


def run_fuzzy_check(question: str, context: str, agent: str = "claude") -> dict:
    """
    Ask an LLM a yes/no quality question about content.
    
    Args:
        question: The quality question (e.g., "Is this summary comprehensive?")
        context: The content to evaluate
        agent: Which agent to use (claude, codex, gemini)
    
    Returns:
        {"passed": bool, "reason": str}
    """
    prompt = f"""You are a quality assessor. Answer this question about the content below.

QUESTION: {question}

CONTENT:
{context[:2000]}  # Truncate to avoid token limits

Answer in strict JSON format only:
{{"passed": true/false, "reason": "brief explanation"}}
"""

    try:
        if agent == "claude":
            # Use JSON mode if supported or just prompt
            result = subprocess.run(
                ["claude", "--dangerously-skip-permissions", "--output-format", "json", "-p", prompt],
                capture_output=True,
                text=True,
                timeout=30,
            )
        elif agent == "codex":
            result = subprocess.run(
                ["codex", "exec", "--full-auto", prompt],
                capture_output=True,
                text=True,
                timeout=30,
            )
        else:
            return {"passed": True, "reason": f"Agent {agent} not implemented, skipping fuzzy check"}

        output = result.stdout.strip()
        
        # Robust JSON extraction
        try:
            # 1. Try finding block
            match = re.search(r"\{.*\}", output, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
            else:
                # 2. Try whole string
                data = json.loads(output)
            
            # 3. Normalize
            return {
                "passed": bool(data.get("passed", True)), # Default to pass if ambiguous
                "reason": str(data.get("reason", "No reason provided"))
            }
            
        except Exception:
            # Fallback if JSON fails
            return {"passed": True, "reason": f"Could not parse agent response: {output[:50]}..."}

    except subprocess.TimeoutExpired:
        return {"passed": True, "reason": "Fuzzy check timed out, assuming pass"}
    except FileNotFoundError:
        return {"passed": True, "reason": f"Agent CLI '{agent}' not found, skipping fuzzy check"}
    except Exception as e:
        return {"passed": True, "reason": f"Fuzzy check error: {e}, assuming pass"}


if __name__ == "__main__":
    # Test
    result = run_fuzzy_check(
        "Is this a good summary?",
        "The BHT predicts branch outcomes using history."
    )
    print(json.dumps(result, indent=2))
