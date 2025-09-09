"""
Module: llm_mathblock.py

External Dependencies:
- concurrent: [Documentation URL]
- pydantic: https://docs.pydantic.dev/
- tqdm: [Documentation URL]
- marker: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Annotated, Optional
import asyncio
import os

from pydantic import BaseModel
from tqdm import tqdm
from loguru import logger

from extractor.core.output import json_to_html, unwrap_outer_tag
from extractor.core.processors.llm import BaseLLMComplexBlockProcessor

from extractor.core.schema import BlockTypes
from extractor.core.schema.blocks import Block, InlineMath
from extractor.core.schema.document import Document
from extractor.core.schema.groups import PageGroup



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

class LLMMathBlockProcessor(BaseLLMComplexBlockProcessor):
    redo_inline_math: Annotated[
        bool,
        "If True, the inline math will be re-done, otherwise it will be left as is.",
    ] = False
    inlinemath_min_ratio: Annotated[
        float,
        "If more than this ratio of blocks are inlinemath blocks, assume everything has math.",
    ] = 0.4

    block_types = (BlockTypes.TextInlineMath,)  # Primary block type
    additional_block_types = (
        BlockTypes.Text,
        BlockTypes.Caption,
        BlockTypes.SectionHeader,
        BlockTypes.Footnote,
    )  # Seconday, can also contain math

    text_math_rewriting_prompt = """You are a text correction expert specializing in accurately reproducing text from images.
You will receive an image of a text block and extracted text corresponding to the text in the image.
Your task is to correct any errors in the extracted text, including math, formatting, and other inaccuracies, and output the corrected block in html format.  Stay as faithful to the text in the image as possible.

**Instructions:**

1. Carefully examine the provided text block image .
2. Analyze the text that has been extracted from the block.
3. Compare the extracted text to the corresponding text in the image.
4. Write a short analysis of the text block, including any errors you see in the extracted text.
5. If there are no errors in any of the extracted text, output "No corrections needed".
6. Correct any errors in the extracted text, including:
    * Inline math: Ensure all mathematical expressions are correctly formatted and rendered.  Surround them with <math>...</math> tags.  The math expressions should be rendered in simple, concise, KaTeX-compatible LaTeX.  Do not use $ or $$ as delimiters.
    * If a math expression is not in LaTeX format, convert it to LaTeX format, and surround it with <math>...</math> tags.
    * Formatting: Maintain consistent formatting with the text block image, including spacing, indentation, subscripts/superscripts, and special characters.  Use the <i>, <b>, <sup>, <sub>, and <span> tags to format the text as needed.
    * Other inaccuracies:  If the image is handwritten then you may correct any spelling errors, or other discrepancies.
    * Ensure lines wrap properly, and that newlines are not in the middle of sentences.
7. Do not remove any formatting i.e bold, italics, math, superscripts, subscripts, etc from the extracted text unless it is necessary to correct an error.
8. Output the corrected text in html format, as shown in the example below.  Only use the p, math, br, a, i, b, sup, sub, and span tags.
9. You absolutely cannot remove any <a href='#...'>...</a> tags, those are extremely important for references and are coming directly from the document, you MUST always preserve them.

**Example:**

Input:
```html
Adversarial training (AT) <a href='#page-9-1'>[23]</a>, which aims to minimize the model's risk under the worst-case perturbations, '
is currently the most effective approach for improving the robustness of deep neural networks. For a given neural network f(x, w) 
with parameters w, the optimization objective of AT can be formulated as follows:
```

Output:
analysis: The inline math is not in LaTeX format and is not surrounded by <math>...</math> tags.
```html
Adversarial training <i>(AT)</i> <a href='#page-9-1'>[23]</a>, which aims to minimize the model's risk under the worst-case perturbations, is currently the most effective approach for improving the robustness of deep neural networks. For a given neural network <math>f(x, w)</math> with parameters <math>w</math>, the optimization objective of AT can be formulated as follows:'
```

**Input:**
```html
{extracted_html}
```
"""

    def rewrite_blocks(self, document: Document):
        if not self.redo_inline_math:
            return

        # Get inline math blocks
        inline_blocks: List[InlineMath] = [
            (page, block)
            for page in document.pages
            for block in page.contained_blocks(document, self.block_types)
        ]

        # Get other blocks with detected math in them
        detected_blocks = [
            (page, block)
            for page in document.pages
            for block in page.contained_blocks(
                document,
                (
                    BlockTypes.Text,
                    BlockTypes.Caption,
                    BlockTypes.SectionHeader,
                    BlockTypes.Footnote,
                    BlockTypes.ListItem,
                ),
            )
            if any(
                [
                    b.formats and "math" in b.formats
                    for b in block.contained_blocks(document, (BlockTypes.Line,))
                ]
            )
        ]

        # If a page has enough math blocks, assume all blocks can contain math
        additional_text_blocks = []
        for page in document.pages:
            # Check for inline math blocks
            page_inlinemath_blocks = [
                im for im in inline_blocks if im[0].page_id == page.page_id
            ]
            page_detected_blocks = [
                db for db in detected_blocks if db[0].page_id == page.page_id
            ]
            math_block_count = len(page_inlinemath_blocks) + len(page_detected_blocks)

            # Find all potential blocks
            additional_blocks = page.contained_blocks(
                document, self.additional_block_types + self.block_types
            )

            # Check if the ratio of math blocks to additional blocks is high enough
            if (
                math_block_count / max(1, len(additional_blocks))
                < self.inlinemath_min_ratio
            ):
                continue

            for b in additional_blocks:
                if b not in detected_blocks and b not in inline_blocks:
                    additional_text_blocks.append((page, b))

        inference_blocks = inline_blocks + detected_blocks + additional_text_blocks

        # Don't show progress if there are no blocks to process
        total_blocks = len(inference_blocks)
        if total_blocks == 0:
            return

        pbar = tqdm(
            desc=f"{self.__class__.__name__} running", disable=self.disable_tqdm
        )
        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            for future in as_completed(
                [
                    executor.submit(self.process_rewriting, document, b[0], b[1])
                    for b in inference_blocks
                ]
            ):
                future.result()  # Raise exceptions if any occurred
                pbar.update(1)

        pbar.close()

    def get_block_text(self, block: Block, document: Document) -> str:
        html = json_to_html(block.render(document))
        html = unwrap_outer_tag(html)  # Remove an outer p tag if it exists
        return html

    def get_block_lines(self, block: Block, document: Document) -> Tuple[list, list]:
        text_lines = block.contained_blocks(document, (BlockTypes.Line,))
        extracted_lines = [line.formatted_text(document) for line in text_lines]
        return text_lines, extracted_lines

    def process_rewriting(self, document: Document, page: PageGroup, block: Block):
        block_text = self.get_block_text(block, document)
        prompt = self.text_math_rewriting_prompt.replace("{extracted_html}", block_text)

        image = self.extract_image(document, block)
        response = call_claude_subprocess_sync(prompt)

        if not response or "corrected_html" not in response:
            block.update_metadata(llm_error_count=1)
            self.add_validation_to_block(block, True, 'LLM response missing or malformed')
            return

        corrected_html = response["corrected_html"]
        if not corrected_html:
            block.update_metadata(llm_error_count=1)
            self.add_validation_to_block(block, True, 'Empty LLM response')
            return

        # Enhanced suspicious detection for math block processing
        suspicious_reasons = []
        
        # Block is fine
        if "no corrections needed" in corrected_html.lower():
            return

        # Check for short response
        if len(corrected_html) < len(block_text) * 0.6:
            suspicious_reasons.append("LLM returned significantly shorter response")
        
        # Check for error messages
        error_indicators = ["error", "failed", "cannot", "unable", "sorry", "invalid"]
        html_lower = corrected_html.lower()
        for indicator in error_indicators:
            if indicator in html_lower and len(corrected_html) < 200:
                suspicious_reasons.append(f"LLM may have returned error: '{indicator}'")
        
        # Check for math tag issues
        math_open = corrected_html.count("<math")
        math_close = corrected_html.count("</math>")
        if math_open != math_close:
            suspicious_reasons.append("Unbalanced math tags")
        
        # Check for basic HTML structure
        if "<" not in corrected_html or ">" not in corrected_html:
            suspicious_reasons.append("Response lacks HTML structure")
        
        # Set suspicious flag if any issues found
        if suspicious_reasons:
            self.add_validation_to_block(block, True, '"; ".join(suspicious_reasons)')
            block.update_metadata(llm_error_count=1)
            return

        block.html = corrected_html


class LLMTextSchema(BaseModel):
    analysis: str
    corrected_html: str
