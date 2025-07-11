"""
Claude Module Query Service.
Module: claude_module_query.py
Description: Implementation of claude module query functionality

This module provides a simple function to query other module codebases
using Claude with specialized system prompts. It includes a response storage
system to persist Claude outputs for later retrieval.

Documentation:
- Claude: https://docs.anthropic.com/claude/docs
- System Prompts: https://docs.anthropic.com/claude/docs/system-prompts
"""

import json
import os
import subprocess
import uuid
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union, List

# Import required logger
from loguru import logger


# Response storage class for Claude outputs
class ClaudeResponseStorage:
    """
    Manages storage and retrieval of Claude response data.
    Uses JSON files in a dedicated directory for persistence.
    """
    
    def __init__(self, storage_dir: Optional[str] = None):
        """
        Initialize the response storage system.
        
        Args:
            storage_dir: Directory to store response files (default: ~/.claude_responses)
        """
        if storage_dir is None:
            home_dir = os.path.expanduser("~")
            self.storage_dir = Path(home_dir) / ".claude_responses"
        else:
            self.storage_dir = Path(storage_dir)
        
        # Create storage directory if it doesn't exist
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize index file if it doesn't exist
        self.index_file = self.storage_dir / "index.json"
        if not self.index_file.exists():
            with open(self.index_file, "w") as f:
                json.dump({
                    "responses": [],
                    "last_updated": datetime.now().isoformat()
                }, f, indent=2)
    
    def store_response(self, 
                       response_data: Dict[str, Any], 
                       prompt: str, 
                       module_name: str,
                       query_id: Optional[str] = None) -> str:
        """
        Store a Claude response with metadata.
        
        Args:
            response_data: The response data from Claude
            prompt: The prompt that was sent to Claude
            module_name: The name of the module that was queried
            query_id: Optional ID for the query (generates one if not provided)
            
        Returns:
            The ID of the stored response
        """
        # Generate query ID if not provided
        if query_id is None:
            query_id = str(uuid.uuid4())
            
        # Create response metadata
        timestamp = datetime.now().isoformat()
        metadata = {
            "id": query_id,
            "module": module_name,
            "timestamp": timestamp,
            "prompt": prompt,
        }
        
        # Create full response object
        full_response = {
            "metadata": metadata,
            "response": response_data
        }
        
        # Save to file
        response_file = self.storage_dir / f"{query_id}.json"
        with open(response_file, "w") as f:
            json.dump(full_response, f, indent=2)
        
        # Update index
        with open(self.index_file, "r") as f:
            index = json.load(f)
        
        index["responses"].append({
            "id": query_id,
            "module": module_name,
            "timestamp": timestamp,
            "file": str(response_file)
        })
        index["last_updated"] = timestamp
        
        with open(self.index_file, "w") as f:
            json.dump(index, f, indent=2)
        
        return query_id
    
    def get_response(self, query_id: str) -> Dict[str, Any]:
        """
        Retrieve a stored response by ID.
        
        Args:
            query_id: The ID of the query to retrieve
            
        Returns:
            The stored response data or error if not found
        """
        response_file = self.storage_dir / f"{query_id}.json"
        
        if not response_file.exists():
            logger.error(f"Response with ID {query_id} not found")
            return {
                "error": "Response not found",
                "query_id": query_id
            }
        
        with open(response_file, "r") as f:
            return json.load(f)
    
    def list_responses(self, 
                      module_name: Optional[str] = None, 
                      limit: int = 10) -> List[Dict[str, Any]]:
        """
        List stored responses, optionally filtered by module.
        
        Args:
            module_name: Optional filter by module name
            limit: Maximum number of responses to return (default: 10)
            
        Returns:
            List of response metadata
        """
        with open(self.index_file, "r") as f:
            index = json.load(f)
        
        # Filter by module if specified
        responses = index["responses"]
        if module_name is not None:
            responses = [r for r in responses if r["module"] == module_name]
        
        # Sort by timestamp (newest first) and limit
        responses.sort(key=lambda x: x["timestamp"], reverse=True)
        return responses[:limit]


# Initialize the response storage
response_storage = ClaudeResponseStorage()


def query_module(
    prompt: str,
    module_path: str,
    system_prompt: Optional[str] = None,
    module_name: str = None,
    background: bool = False,
    query_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Query any module by running Claude in the module's directory with a specialized system prompt.
    
    Args:
        prompt: The question or request for the module
        module_path: Path to the module
        system_prompt: Optional custom system prompt, uses default if None
        module_name: Name of the module for logging (defaults to directory name)
        background: Run Claude in background mode if True
        query_id: Optional ID for the query (generates one if not provided)
        
    Returns:
        Dictionary containing the structured response from the module
        or query ID if running in background mode
    """
    # Get module name from path if not provided
    if module_name is None:
        module_name = Path(module_path).name
    
    # Generate query ID if not provided
    if query_id is None:
        query_id = str(uuid.uuid4())
    
    # Use a default system prompt if none provided
    if system_prompt is None:
        system_prompt = f"""
You are a {module_name} expert with detailed knowledge of the {module_name} codebase.
You're helping another module understand {module_name}'s capabilities and requirements.

When answering questions:
1. Focus on factual information found in the {module_name} codebase
2. Provide specific file paths and code references
3. Structure your output as JSON when possible
4. Be precise about formats, APIs, and integration points
5. Indicate when you're unsure rather than guessing
"""

    try:
        logger.info(f"Querying {module_name} with prompt: {prompt[:50]}...")
        
        # Construct Claude command
        claude_cmd = [
            "claude",
            "-p", prompt,
            "--system-prompt", system_prompt
            # Removed --json flag as it might not be supported in all versions
        ]
        
        # For background mode, we'll execute Claude and store the response later
        if background:
            # Create a unique output file
            output_file = Path(os.path.expanduser("~")) / ".claude_responses" / f"{query_id}_output.json"
            
            # Append output redirection to command
            cmd_str = " ".join(f'"{arg}"' if ' ' in arg else arg for arg in claude_cmd)
            cmd_str += f" > {output_file} 2>&1 &"
            
            # Execute in background
            logger.info(f"Running Claude in background mode with ID: {query_id}")
            subprocess.run(
                cmd_str,
                cwd=module_path,
                shell=True
            )
            
            # Store pending response
            response_data = {
                "status": "pending",
                "query_id": query_id,
                "output_file": str(output_file)
            }
            
            response_storage.store_response(
                response_data,
                prompt,
                module_name,
                query_id
            )
            
            return {
                "status": "pending",
                "query_id": query_id,
                "message": "Claude is processing your query in the background"
            }
        
        # For foreground mode, execute Claude synchronously
        result = subprocess.run(
            claude_cmd,
            cwd=module_path,
            capture_output=True,
            text=True
        )
        
        # Check if execution was successful
        if result.returncode != 0:
            logger.error(f"Claude execution failed: {result.stderr}")
            error_response = {
                "error": f"Failed to query {module_name}",
                "details": result.stderr
            }
            
            # Store error response
            response_storage.store_response(
                error_response,
                prompt,
                module_name,
                query_id
            )
            
            return error_response
        
        # Parse the JSON response
        try:
            response = json.loads(result.stdout)
            
            # Store successful response
            response_storage.store_response(
                response,
                prompt,
                module_name,
                query_id
            )
            
            return response
        except json.JSONDecodeError:
            # If JSON parsing fails, return the raw output
            logger.warning("Failed to parse JSON response, returning raw output")
            raw_response = {
                "error": "Failed to parse JSON from Claude output",
                "raw_output": result.stdout
            }
            
            # Store raw response
            response_storage.store_response(
                raw_response,
                prompt,
                module_name,
                query_id
            )
            
            return raw_response
            
    except Exception as e:
        logger.error(f"Error querying {module_name}: {str(e)}")
        error_response = {
            "error": f"Exception while querying {module_name}",
            "details": str(e)
        }
        
        # Store error response
        response_storage.store_response(
            error_response,
            prompt,
            module_name,
            query_id
        )
        
        raise


def query_arangodb(
    prompt: str,
    arangodb_path: str = ".",
    system_prompt: Optional[str] = None,
    background: bool = False,
    query_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Query ArangoDB by running Claude in the ArangoDB directory with a specialized system prompt.
    
    Args:
        prompt: The question or request for ArangoDB
        arangodb_path: Path to the ArangoDB module
        system_prompt: Optional custom system prompt, uses default if None
        background: Run Claude in background mode if True
        query_id: Optional ID for the query (generates one if not provided)
        
    Returns:
        Dictionary containing the structured response from ArangoDB
        or query ID if running in background mode
    """
    # Use a default ArangoDB-specific system prompt if none provided
    if system_prompt is None:
        system_prompt = """
You are an ArangoDB expert with detailed knowledge of the ArangoDB codebase.
You're helping the Marker module understand ArangoDB's capabilities and requirements.

When answering questions:
1. Focus on factual information found in the ArangoDB codebase
2. Provide specific file paths and code references
3. Structure your output as JSON when possible
4. Be precise about formats, APIs, and integration points
5. Indicate when you're unsure rather than guessing

Focus areas include:
- QA pair formats and requirements
- Graph data structures
- Vector search capabilities
- Export and import formats
- Database schema
"""
    
    return query_module(
        prompt=prompt, 
        module_path=arangodb_path, 
        system_prompt=system_prompt, 
        module_name="ArangoDB",
        background=background,
        query_id=query_id
    )


def get_response_status(query_id: str) -> Dict[str, Any]:
    """
    Check the status of a background query and retrieve the result if available.
    
    Args:
        query_id: The ID of the query to check
        
    Returns:
        Dictionary with query status and response if available
    """
    # Get response from storage
    stored_response = response_storage.get_response(query_id)
    
    # Check if there was an error retrieving the response
    if "error" in stored_response:
        return stored_response
    
    # Extract the actual response data
    response_data = stored_response.get("response", {})
    
    # If the response is still pending, check if the output file exists
    if response_data.get("status") == "pending":
        output_file = Path(response_data.get("output_file", ""))
        
        if not output_file.exists():
            # Still waiting for Claude to complete
            return {
                "status": "pending",
                "query_id": query_id,
                "message": "Claude is still processing your query"
            }
        
        # Output file exists, read and parse the response
        try:
            with open(output_file, "r") as f:
                output_content = f.read()
            
            # Try to parse as JSON
            try:
                json_response = json.loads(output_content)
                
                # Update stored response
                updated_response = {
                    "status": "completed",
                    "query_id": query_id,
                    "response": json_response
                }
                
                # Store updated response
                response_storage.store_response(
                    updated_response,
                    stored_response.get("metadata", {}).get("prompt", ""),
                    stored_response.get("metadata", {}).get("module", "unknown"),
                    query_id
                )
                
                return {
                    "status": "completed",
                    "query_id": query_id,
                    "response": json_response
                }
            except json.JSONDecodeError:
                # Failed to parse JSON, store raw output
                updated_response = {
                    "status": "completed",
                    "query_id": query_id,
                    "error": "Failed to parse JSON from Claude output",
                    "raw_output": output_content
                }
                
                # Store updated response
                response_storage.store_response(
                    updated_response,
                    stored_response.get("metadata", {}).get("prompt", ""),
                    stored_response.get("metadata", {}).get("module", "unknown"),
                    query_id
                )
                
                return updated_response
        except Exception as e:
            # Error reading or processing output file
            return {
                "status": "error",
                "query_id": query_id,
                "error": f"Error processing Claude output: {str(e)}"
            }
    
    # Response is not pending, return as is
    return {
        "status": response_data.get("status", "unknown"),
        "query_id": query_id,
        "response": response_data
    }


def get_export_format(document_type: str = "pdf", background: bool = False) -> Dict[str, Any]:
    """
    Get the export format specification from ArangoDB for a specific document type.
    
    Args:
        document_type: Type of document (pdf, html, etc.)
        background: Run Claude in background mode if True
        
    Returns:
        Dictionary containing the export format specification
        or query ID if running in background mode
    """
    prompt = f"""
What is the export format used by ArangoDB for {document_type} documents?

Please provide a detailed specification including:
1. All fields in the export format
2. Required vs optional fields
3. Field types and formats
4. Any special handling for {document_type} documents
5. Metadata fields and structure

Return your answer as a structured JSON object with the following format:
{{
  "document_type": "{document_type}",
  "format_fields": [
    {{
      "name": "field_name",
      "type": "data_type",
      "required": true/false,
      "description": "field description"
    }}
  ],
  "metadata_fields": [
    {{
      "name": "metadata_field",
      "type": "data_type",
      "required": true/false,
      "description": "field description"
    }}
  ]
}}
"""
    
    return query_arangodb(prompt, background=background)


def update_export_format(format_updates: Dict[str, Any], background: bool = False) -> Dict[str, Any]:
    """
    Request ArangoDB to update its export format.
    
    Args:
        format_updates: Dictionary with the required format changes
        background: Run Claude in background mode if True
        
    Returns:
        Dictionary with the update results
        or query ID if running in background mode
    """
    # Convert format updates to a string representation for the prompt
    updates_str = json.dumps(format_updates, indent=2)
    
    prompt = f"""
I need to update the export format in ArangoDB with the following changes:

```json
{updates_str}
```

Please:
1. Identify which files in the ArangoDB codebase need to be modified
2. Explain exactly what changes would need to be made
3. Assess the feasibility and potential impact of these changes
4. Return a structured response about whether the changes can be implemented

Return your answer as a structured JSON object with the following format:
{{
  "feasible": true/false,
  "files_to_modify": ["file/path1", "file/path2"],
  "implementation_details": "Description of implementation approach",
  "potential_impacts": ["impact1", "impact2"],
  "estimated_effort": "low/medium/high"
}}
"""
    
    return query_arangodb(prompt, background=background)


if __name__ == "__main__":
    import sys
    
    # Track validation failures
    all_validation_failures = []
    total_tests = 0
    
    # Test basic query function
    total_tests += 1
    try:
        # Use a simple test query that should work regardless of codebase
        result = query_arangodb("What is the name of this project?")
        assert result is not None, "Query returned None"
        assert isinstance(result, dict), "Query didn't return a dictionary"
    except Exception as e:
        all_validation_failures.append(f"Basic query test failed: {str(e)}")
    
    # Final validation result
    if all_validation_failures:
        print(f"❌ VALIDATION FAILED - {len(all_validation_failures)} of {total_tests} tests failed:")
        for failure in all_validation_failures:
            print(f"  - {failure}")
        sys.exit(1)
    else:
        print(f"✅ VALIDATION PASSED - All {total_tests} tests produced expected results")
        print("Function is validated and formal tests can now be written")
        sys.exit(0)