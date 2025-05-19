"""LLM-based summarization for GitGet repository analysis.

This module provides functionality for generating summaries of repository content
using Large Language Models. It handles the interaction with LLM APIs, processes
responses, and formats the results for consumption by other parts of the system.

Key features:
1. LLM-based repository summarization
2. Response processing and validation
3. JSON parsing and cleaning
4. Chunk-based summarization for large repositories

Sample Input:
    ```python
    # # from gitget.summarization import llm_summarize
    
    llm_summarize(
        digest_path="/path/to/DIGEST.txt",
        summary_path="/path/to/output/LLM_SUMMARY.txt",
        model="gemini-2.5-pro-preview-03-25"
    )
    ```

Expected Output:
    A file at the specified summary_path containing a structured summary of the repository with:
    - Overall repository summary
    - Table of contents 
    - Key sections and their descriptions
"""

import os
import json
import textwrap
import asyncio
import tempfile
from typing import Dict, Any, Optional, List, Union
import litellm
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
from pydantic import BaseModel, ValidationError

# Import local utilities
from arangodb.core.utils.json_utils import clean_json_string, json_to_markdown
from arangodb.core.utils.initialize_litellm_cache import initialize_litellm_cache

# Import text processing and workflow tracking
from arangodb.core.utils.text_chunker import count_tokens_with_tiktoken
from arangodb.core.utils.workflow_tracking import (
    track_repo_summarization, RepositoryWorkflow, 
    ComponentType, LogLevel
)

# Initialize LiteLLM cache
initialize_litellm_cache()

# Define the RepoSummary pydantic model
class RepoSummary(BaseModel):
    """Model for repository summary data returned by LLM"""
    summary: str
    table_of_contents: List[str]
    key_sections: Optional[List[Dict[str, str]]] = None
    
    model_config = {
        "arbitrary_types_allowed": True
    }


# LLM summarization function
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
@track_repo_summarization
def llm_summarize(
    digest_path: str,
    summary_path: str,
    model: str = "gemini-2.5-pro-preview-03-25",
    google_vertex_project: str = "gen-lang-client-0870473940",
    google_vertex_location: str = "us-central1",
    output_format: str = "markdown",
    repo_workflow=None
):
    """
    Generate an LLM-based summary of a repository based on its digest content.
    
    This function reads a digest file containing repository content and generates
    a structured summary using an LLM. The summary includes key components, structure,
    and important sections of the repository.
    
    Args:
        digest_path: Path to the digest file
        summary_path: Path where the summary will be saved
        model: LLM model to use (default: gemini-2.5-pro-preview-03-25)
        google_vertex_project: Google Vertex AI project ID
        google_vertex_location: Google Vertex AI location
        output_format: Output format (markdown or json)
        repo_workflow: Repository workflow tracker (injected by decorator)
        
    Returns:
        None (writes summary to file)
        
    Raises:
        FileNotFoundError: If the digest file doesn't exist
        ValidationError: If LLM output can't be parsed as a valid RepoSummary
        
    Example:
        ```python
        llm_summarize(
            digest_path="/repos/python-arango_sparse/DIGEST.txt",
            summary_path="/repos/python-arango_sparse/LLM_SUMMARY.txt",
            model="gemini-2.5-pro-preview-03-25"
        )
        ```
    """
    # Try to import the advanced summarizer
    try:
        # # from gitget.llm_summarizer import summarize_text
        advanced_summarizer_available = True
        logger.info("Using advanced LLM summarizer for repository summarization")
    except ImportError:
        advanced_summarizer_available = False
        logger.warning("Advanced LLM summarizer not available, falling back to standard method")

    with open(digest_path, "r", encoding="utf-8") as f:
        digest_text = f.read()
    
    # Log digest stats if workflow tracking is available
    if repo_workflow:
        digest_size = len(digest_text.encode('utf-8'))
        digest_tokens = count_tokens_with_tiktoken(digest_text, model=model)
        repo_workflow.workflow_logger.log_data(
            {
                "digest_size_bytes": digest_size,
                "digest_tokens": digest_tokens,
                "model": model
            },
            level=LogLevel.INFO,
            source=ComponentType.LLM,
            description="Preparing LLM request"
        )
        repo_workflow.workflow_logger.complete_step("Read repository digest")

    system_prompt = (
        "You are an expert technical documentation summarizer. "
        "You are also a JSON validator. You will only output valid JSON. "
        "When summarizing, incorporate any code metadata (e.g., function names, parameters, docstrings) provided."
    )
    
    # Define our custom summarization prompt
    final_summary_prompt = (
        "Analyze the following repository content, including code metadata where available. "
        "Extract the key concepts, functionalities, and structure. Then generate a structured JSON "
        "response with the following fields:\n"
        "- summary: A concise, clear summary of the repository for technical users, highlighting key functions.\n"
        "- table_of_contents: An ordered list of file or section names that represent the structure of the repository.\n"
        "- key_sections: A list of the most important files or sections, with a 1-2 sentence description for each.\n\n"
        "Format your response as valid JSON, and only output the JSON."
    )
    
    user_prompt = textwrap.dedent(f"""
        Given the following repository content, including code metadata where available, return a JSON object with:
        - summary: A concise, clear summary of the repository for technical users, highlighting key functions if metadata is present.
        - table_of_contents: An ordered list of file or section names that represent the structure of the repository.
        - key_sections: (optional) A list of the most important files or sections, with a 1-2 sentence description for each.

        Format your response as valid JSON. Only output the JSON.

        Repository content:
        {digest_text}
    """)

    try:
        # Use advanced summarizer if available
        if advanced_summarizer_available:
            logger.info(f"Using advanced text summarizer with {model} model...")
            
            # Configure the advanced summarizer
            config = {
                "model": model,
                "temperature": 0.7,
                "context_limit_threshold": 6000,  # Handle larger context since we're using Gemini
                "chunk_size": 5500,               # Larger chunks for repository digest
                "overlap_size": 3,                # Slightly more overlap for better continuity
                "final_summary_prompt": final_summary_prompt,
                "google_vertex_project": google_vertex_project,
                "google_vertex_location": google_vertex_location
            }
            
            # Run the async summarization in the event loop
            summary_content = asyncio.run(summarize_text(digest_text, config))
            
            # Process the content to ensure it's valid JSON
            try:
                # First check if the output is already valid JSON (the advanced summarizer should return structured JSON)
                parsed_json = json.loads(summary_content)
                content = parsed_json
            except json.JSONDecodeError:
                # If not valid JSON, clean it (handle the case where the model returned markdown or explanations)
                content = clean_json_string(summary_content, return_dict=True)
        else:
            # Log LLM request start with standard approach
            if repo_workflow:
                prompt_tokens = count_tokens_with_tiktoken(system_prompt + user_prompt, model=model)
                repo_workflow.log_llm_request(model, prompt_tokens, len(user_prompt))
            
            # Use standard litellm approach
            response = litellm.completion(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                google_vertex_project=google_vertex_project,
                google_vertex_location=google_vertex_location,
            )
            
            # Complete the LLM request step if workflow tracking is available
            if repo_workflow:
                repo_workflow.workflow_logger.complete_step("Process content with LLM")
            
            if hasattr(response, "choices"):
                content_text = response.choices[0].message.content
            elif isinstance(response, str):
                content_text = response
            else:
                content_text = str(response)

            content = clean_json_string(content_text, return_dict=True)

        # Validate against our model and save
        try:
            parsed = RepoSummary.model_validate(content)
            summary_json = json.dumps(parsed.model_dump(), indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Failed to parse or validate LLM output: {e}")
            summary_json = json.dumps({"error": "Failed to parse or validate LLM output", "raw": str(content)})

        if output_format == "json":
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(summary_json)
            logger.info(f"LLM summary saved to {summary_path} (JSON format)")
            
            # Log completion if workflow tracking is available
            if repo_workflow:
                repo_workflow.workflow_logger.log_data(
                    {"summary_path": summary_path, "format": "json"},
                    level=LogLevel.SUCCESS,
                    source=ComponentType.LLM,
                    description="LLM summary saved"
                )
                repo_workflow.workflow_logger.complete_step("Save LLM summary")
        else:
            with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as tmp_json:
                tmp_json.write(summary_json)
                tmp_json_path = tmp_json.name

            try:
                markdown_content = json_to_markdown(parsed.model_dump())
                with open(summary_path, "w", encoding="utf-8") as f:
                    f.write(markdown_content)
                    logger.info(f"LLM summary saved to {summary_path} (Markdown format)")
                
                # Log completion if workflow tracking is available
                if repo_workflow:
                    repo_workflow.workflow_logger.log_data(
                        {"summary_path": summary_path, "format": "markdown"},
                        level=LogLevel.SUCCESS,
                        source=ComponentType.LLM,
                        description="LLM summary saved"
                    )
                    repo_workflow.workflow_logger.complete_step("Save LLM summary")
            finally:
                os.remove(tmp_json_path)

    except Exception as e:
        logger.error(f"LLM summarization failed: {e}")
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"error": str(e)}))
        raise
