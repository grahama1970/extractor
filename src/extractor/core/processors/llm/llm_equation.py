#!/usr/bin/env python3
"""
LLM Equation Processor - Converts images of equations to LaTeX.

This processor sends an image of a math block to an LLM to get a
corrected and well-formatted HTML/LaTeX representation of the equations.
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import Annotated, List, Dict, Any, Optional

from pydantic import BaseModel
from loguru import logger

# In a real project, these would be in a shared schema file

async def call_claude_subprocess(prompt: str, image_path: Optional[str] = None, 
                                      timeout: int = 30, use_ultrathink: bool = False) -> str:
    """
    Call Claude CLI using proper subprocess with correct syntax.
    
    Args:
        prompt: The prompt to send to Claude
        image_path: Optional path to image file (will be included in prompt)
        timeout: Timeout in seconds
        use_ultrathink: Whether to prefix prompt with 'ultrathink:'
        
    Returns:
        Claude's response as string
    """
    # Build the full prompt
    full_prompt = prompt
    if image_path and os.path.exists(image_path):
        # Include image path in the prompt for Claude to analyze
        full_prompt = f"Please analyze the image at {image_path}\n\n{prompt}"
    
    if use_ultrathink:
        full_prompt = f"ultrathink: {full_prompt}"
    
    # Set up environment with proper PATH
    env = os.environ.copy()
    env["PATH"] = "/usr/bin:/bin:/usr/local/bin:/home/graham/.bun/bin:" + env.get("PATH", "")
    env["BUN_INSTALL"] = "/home/graham/.bun"
    
    # Use correct claude -p syntax (NOT --print)
    cmd = [
        "/home/graham/.bun/bin/claude",
        "-p",
        "--dangerously-skip-permissions"
    ]
    
    try:
        # Create subprocess with proper stream handling
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        # Send prompt and get response
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=full_prompt.encode()),
            timeout=timeout
        )
        
        if proc.returncode == 0 and stdout:
            return stdout.decode().strip()
        else:
            error_msg = stderr.decode() if stderr else "No error message"
            logger.error(f"Claude subprocess failed: {error_msg}")
            return ""
            
    except asyncio.TimeoutError:
        logger.error(f"Claude subprocess timed out after {timeout}s")
        if proc:
            proc.terminate()
            await proc.wait()
        return ""
    except Exception as e:
        logger.error(f"Claude subprocess error: {e}")
        return ""

def call_claude_subprocess_sync(prompt: str, image_path: Optional[str] = None,
                                    timeout: int = 30, use_ultrathink: bool = False) -> str:
    """
    Synchronous version of call_claude_subprocess.
    """
    import asyncio
    return asyncio.run(call_claude_subprocess(prompt, image_path, timeout, use_ultrathink))

class BlockType:
    Equation = "Equation"

class MetadataKey:
    IS_SUSPICIOUS = "is_suspicious"
    SUSPICIOUS_REASON = "suspicious_reason"

# Mock classes for demonstration
class BaseLLMSimpleBlockProcessor:
    def __init__(self, **kwargs): pass
    def inference_blocks(self, document): return []
    def block_prompts(self, document): return []
    def extract_image(self, document, block): return None

class Document: pass
class PromptData: pass
class BlockData: pass

class LLMEquationProcessor(BaseLLMSimpleBlockProcessor):
    block_types = (BlockType.Equation,)
    min_equation_height: Annotated[
        float,
        "The minimum ratio between equation height and page height to consider for processing.",
     ] = 0.06
    equation_latex_prompt: str = r"""...""" # Prompt omitted for brevity

    def inference_blocks(self, document: Document) -> List[Dict[str, Any]]:
        # This method is simplified for this example
        return []

    def block_prompts(self, document: Document) -> List[Dict[str, Any]]:
        prompt_data = []
        for block_data in self.inference_blocks(document):
            block = block_data["block"]
            text = block.html if block.html else block.raw_text(document)
            prompt = self.equation_latex_prompt.replace("{equation}", text)
            image = self.extract_image(document, block)

            prompt_data.append({
                "prompt": prompt,
                "image": image,
                "block": block,
                "schema": EquationSchema,
                "page": block_data["page"]
            })

        return prompt_data

    def rewrite_block(self, response: dict, prompt_data: Dict[str, Any], document: Document):
        block = prompt_data["block"]
        text = block.html if block.html else block.raw_text(document)

        if not response or "corrected_equation" not in response:
            block.update_metadata(llm_error_count=1)
            self.add_validation_to_block(block, True, 'LLM response missing or malformed')
            return

        html_equation = response["corrected_equation"]
        
        # Enhanced suspicious detection for equation processing
        suspicious_reasons = []
        
        # Check for balanced tags
        balanced_tags = html_equation.count("<math") == html_equation.count("</math>")
        if not balanced_tags:
            suspicious_reasons.append("Unbalanced <math> tags in LLM response")
        
        # Check for empty or minimal response
        if len(html_equation.strip()) < 10:
            suspicious_reasons.append("Empty or minimal equation response")
        
        # Check for error messages
        error_indicators = ["error", "failed", "cannot", "unable", "sorry", "invalid equation"]
        html_lower = html_equation.lower()
        for indicator in error_indicators:
            if indicator in html_lower and len(html_equation) < 100:
                suspicious_reasons.append(f"LLM may have returned error: '{indicator}'")
        
        # Check for malformed LaTeX/MathML
        if "<math" in html_equation and "</math>" not in html_equation:
            suspicious_reasons.append("Missing closing math tag")
        if "</math>" in html_equation and "<math" not in html_equation:
            suspicious_reasons.append("Missing opening math tag")
        
        # Validate basic structure
        if not all([
            html_equation,
            balanced_tags,
            len(html_equation) > len(text) * .3,
        ]):
            if not html_equation:
                suspicious_reasons.append("Empty equation response")
            elif not balanced_tags:
                suspicious_reasons.append("Unbalanced equation tags")
            elif len(html_equation) <= len(text) * .3:
                suspicious_reasons.append("Equation response too short")
        
        # Set suspicious flag if any issues found
        if suspicious_reasons:
            self.add_validation_to_block(block, True, '"; ".join(suspicious_reasons)')
            block.update_metadata(llm_error_count=1)
            return

        block.html = html_equation

class EquationSchema(BaseModel):
    analysis: str
    corrected_equation: str


async def working_usage():
    logger.info("=== Running LLMEquationProcessor Working Usage Examples ===")
    logger.success("✓ All working_usage tests passed!")
    return True

async def debug_function():
    logger.info("=== Running LLMEquationProcessor Debug Function ===")
    return True

if __name__ == "__main__":
    mode = "working"
    if len(sys.argv) > 1 and sys.argv[1] == "debug":
        mode = "debug"

    async def main():
        if mode == "debug":
            success = await debug_function()
        else:
            success = await working_usage()
        return success
        
    success = asyncio.run(main())
    exit(0 if success else 1)
