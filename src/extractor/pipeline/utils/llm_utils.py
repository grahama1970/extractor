"""
Simple LLM utility functions using litellm

No complex classes, just simple functions that work!
"""

import os
import base64
from typing import Optional, Dict, Any, Union
from pathlib import Path
from io import BytesIO
from textwrap import dedent

from loguru import logger
from PIL import Image

from scillm import acompletion as scillm_acompletion  # type: ignore

# Import json cleaning utility
from extractor.core.services.utils.json_utils import clean_json_string

# from utils.async_processing import call_llm_with_retry
from extractor.pipeline.utils.litellm_response_utils import extract_content


async def call_llm_with_image(
    prompt: str,
    image: Optional[Union[Image.Image, str, Path]] = None,
    model: str = None,
    temperature: float = 0.1,
    response_format: str = "json",
) -> Optional[Dict[str, Any]]:
    """Simple function to call LLM with text and optional image.

    Args:
        prompt: Text prompt
        image: Optional PIL Image, base64 string, or path
        model: Model to use (defaults to env var or moonshot)
        temperature: Temperature for generation
        response_format: "json" or "text"

    Returns:
        Dict with response or None if failed
    """

    # Default model
    if model is None:
        model = os.getenv("LITELLM_MODEL", "moonshot/kimi-k2-turbo-preview")

    try:
        messages = [{"role": "user", "content": []}]

        # Add text
        messages[0]["content"].append({"type": "text", "text": prompt})

        # Add image if provided
        if image is not None:
            image_base64 = prepare_image_base64(image)
            if image_base64:
                messages[0]["content"].append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                    }
                )

        # Call LLM
        logger.info(f"Calling {model}")

        kwargs = {"model": model, "messages": messages, "temperature": temperature}

        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        # SciLLM async client
        import asyncio as _asyncio
        async def _call():
            return await scillm_acompletion(**kwargs)
        response = _asyncio.run(_call())

        # Extract response
        content = extract_content(response)

        # Parse JSON if expected
        if response_format == "json":
            parsed = clean_json_string(content, return_dict=True)
            if parsed:
                return parsed
            else:
                logger.error("Failed to parse JSON response")
                return {"error": "Invalid JSON", "raw_response": content}
        else:
            return {"response": content}

    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return None


def prepare_image_base64(image: Union[Image.Image, str, Path]) -> Optional[str]:
    """Convert image to base64 string.

    Args:
        image: PIL Image, base64 string, or file path

    Returns:
        Base64 string or None if failed
    """
    try:
        # If already base64
        if isinstance(image, str) and (image.startswith("data:") or len(image) > 1000):
            if image.startswith("data:"):
                return image.split(",")[1]
            return image

        # If path
        if isinstance(image, (str, Path)):
            image = Image.open(image)

        # Convert PIL Image to base64
        if isinstance(image, Image.Image):
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode()

    except Exception as e:
        logger.error(f"Failed to prepare image: {e}")
        return None


async def interpret_annotation_with_llm(
    annotation_text: str, visual_base64: str, page_context: str
) -> Optional[Dict[str, Any]]:
    """Interpret why an annotation was made using LLM.

    Args:
        annotation_text: The annotation text
        visual_base64: Base64 encoded image of annotation area
        page_context: Text context from the page

    Returns:
        Dict with interpretation or None
    """
    prompt = dedent(
        f"""
        You are analyzing a PDF annotation. 

        The annotation text is: "{annotation_text}"

        Page context: {page_context}

        Please provide a JSON response with:
        {{
            "purpose": "Why this specific area was annotated",
            "key_insight": "What key information the annotation highlights",
            "significance": "Why this section matters",
            "category": "Type: definition, important, question, reference, etc.",
            "action_needed": "What action should be taken based on this annotation"
        }}

        Focus on understanding the PURPOSE of the annotation.
    """
    ).strip()

    # Use local model for simple annotation interpretation
    return await call_llm_with_image(
        prompt=prompt,
        image=visual_base64,
        model="ollama/qwen3:14b",  # Local model for simple interpretation
        response_format="json",
    )


async def describe_image_with_llm(
    image_base64: str, caption: Optional[str] = None, section_title: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Get LLM description of an image/figure.

    Args:
        image_base64: Base64 encoded image
        caption: Optional caption text
        section_title: Optional section context

    Returns:
        Dict with description or None
    """
    context = []
    if section_title:
        context.append(f"This image appears in section: {section_title}")
    if caption:
        context.append(f"Caption: {caption}")

    context_str = "\n".join(context) if context else "No additional context available."

    prompt = dedent(
        f"""
        Analyze this technical image/diagram from an engineering PDF.

        Context:
        {context_str}

        Please provide a JSON response with:
        {{
            "type": "The type of visual (diagram, chart, schematic, table, graph, etc.)",
            "description": "Detailed description of what the image shows",
            "key_elements": ["List", "of", "key", "elements", "shown"],
            "purpose": "The purpose of this visual in the document",
            "technical_details": "Any technical specifications or values shown"
        }}
    """
    ).strip()

    return await call_llm_with_image(prompt=prompt, image=image_base64, response_format="json")


async def reflow_section_with_llm(
    section_data: Dict[str, Any], full_context: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Reflow a section using LLM with all available context.

    This is THE CORE function - why we forked marker-pdf!

    Args:
        section_data: The section to reflow
        full_context: All pipeline context (tables, images, annotations)

    Returns:
        Dict with reflowed section or None
    """
    # Build comprehensive prompt with ALL context
    prompt_parts = [
        "You are reflowing a section from an engineering PDF.",
        f"Section title: {section_data.get('title', 'Untitled')}",
        "",
    ]

    # Add text blocks
    if "blocks" in section_data:
        prompt_parts.append("Text blocks:")
        for i, block in enumerate(section_data["blocks"]):
            prompt_parts.append(f"{i+1}. {block.get('text', '')}")
        prompt_parts.append("")

    # Add table context
    if "tables" in full_context:
        prompt_parts.append("Tables in this section:")
        for table in full_context["tables"]:
            prompt_parts.append(f"- Table: {table.get('caption', 'No caption')}")
            prompt_parts.append(f"  Quality: {table.get('quality_score', 0):.2f}")
        prompt_parts.append("")

    # Add image context
    if "images" in full_context:
        prompt_parts.append("Images in this section:")
        for img in full_context["images"]:
            prompt_parts.append(
                f"- {img.get('type', 'Image')}: {img.get('description', 'No description')}"
            )
        prompt_parts.append("")

    # Add annotation context
    if "annotations" in full_context:
        prompt_parts.append("Human annotations indicate:")
        for ann in full_context["annotations"]:
            if "interpretation" in ann:
                prompt_parts.append(f"- {ann['interpretation'].get('purpose', 'Unknown purpose')}")
        prompt_parts.append("")

    prompt_parts.extend(
        [
            "Please reflow this section to:",
            "1. Fix any OCR errors (use context to correct garbled text)",
            "2. Merge split tables that belong together",
            "3. Provide meaningful table titles based on context",
            "4. Group related content into coherent chunks",
            "5. Preserve all technical details and specifications",
            "",
            "Return JSON with:",
            "{",
            '  "reflowed_text": "The complete reflowed section text",',
            '  "merged_tables": [{"title": "...", "data": "..."}],',
            '  "ocr_corrections": {"original": "corrected", ...},',
            '  "structural_changes": "Description of changes made"',
            "}",
        ]
    )

    prompt = "\n".join(prompt_parts)

    return await call_llm_with_image(prompt=prompt, response_format="json")
