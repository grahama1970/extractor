"""
Marker Agent Commands Module

Provides CLI commands for inter-module communication between Marker and ArangoDB.
This module implements the communication mechanism described in inter-module communication documentation.

Links:
- Communication Protocol: docs/correspondence/module_communication.md
- Marker: https://github.com/example/marker

Sample Input/Output:
- Input: Message requests from ArangoDB
- Output: Processed responses and actions in Marker
"""

import os
import sys
import json
import time
import typer
import shutil
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List, Any

# Set up application
app = typer.Typer(
    name="agent",
    help="Inter-module communication commands",
    add_completion=False
)

# Constants
ARANGODB_PATH = "."
MARKER_MESSAGES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "messages")
ARANGODB_MESSAGES_DIR = os.path.join(ARANGODB_PATH, "messages")

# Ensure message directories exist
os.makedirs(os.path.join(MARKER_MESSAGES_DIR, "from_arangodb"), exist_ok=True)
os.makedirs(os.path.join(MARKER_MESSAGES_DIR, "to_arangodb"), exist_ok=True)
os.makedirs(os.path.join(ARANGODB_MESSAGES_DIR, "from_marker"), exist_ok=True)
os.makedirs(os.path.join(ARANGODB_MESSAGES_DIR, "to_marker"), exist_ok=True)


@app.command("process-message")
def process_message(
    message_file: Path = typer.Argument(..., help="Path to message file from ArangoDB")
):
    """
    Process a message from ArangoDB module.
    
    This command reads a message from ArangoDB, analyzes it using Claude Code,
    and takes appropriate actions in Marker.
    """
    # Check if message file exists
    if not message_file.exists():
        typer.echo(f"Error: Message file not found: {message_file}")
        raise typer.Exit(code=1)
    
    typer.echo(f"Processing message from file: {message_file}")
    
    # Read message
    try:
        with open(message_file, 'r') as f:
            message = json.load(f)
    except json.JSONDecodeError:
        typer.echo("Error: Invalid JSON in message file")
        raise typer.Exit(code=1)
    
    # Validate message format
    if not all(field in message for field in ["source", "target", "type", "content"]):
        typer.echo("Error: Invalid message format. Required fields: source, target, type, content")
        raise typer.Exit(code=1)
    
    # Check message source
    if message["source"] != "arangodb":
        typer.echo(f"Error: Invalid message source: {message['source']}. Expected: arangodb")
        raise typer.Exit(code=1)
    
    # Process the message (for demonstration, just print the content)
    typer.echo(f"Message content: {message['content']}")
    
    # Create a response
    response = {
        "source": "marker",
        "target": "arangodb",
        "type": "response",
        "content": "Thank you for your message. Here's information about our PDF export format.",
        "timestamp": datetime.now().isoformat(),
        "metadata": {
            "request_timestamp": message.get("timestamp"),
            "pdf_export_info": {
                "format_version": "1.0",
                "structure": {
                    "document": {
                        "id": "unique identifier",
                        "title": "document title",
                        "metadata": {
                            "author": "author name",
                            "date": "creation date",
                            "source": "source information"
                        },
                        "pages": [
                            {
                                "page_num": 0,
                                "blocks": [
                                    {
                                        "block_id": "unique block id",
                                        "type": "text/table/image/section_header",
                                        "text": "content text",
                                        "position": {
                                            "top": 0,
                                            "left": 0,
                                            "width": 0,
                                            "height": 0
                                        },
                                        "section_hash": "section identifier (for section headers)"
                                    }
                                ]
                            }
                        ]
                    },
                    "raw_corpus": {
                        "full_text": "entire document text",
                        "pages": ["page 1 text", "page 2 text"]
                    }
                },
                "processing_steps": [
                    "PDF parsing with PyMuPDF",
                    "Text extraction with layout analysis",
                    "Section hierarchy detection",
                    "Table and image extraction",
                    "JSON serialization with Pydantic models"
                ],
                "renderer_formats": [
                    "ArangoDB format",
                    "JSONL format",
                    "Markdown format"
                ]
            }
        }
    }
    
    # Save response to ArangoDB's incoming directory
    response_file = os.path.join(ARANGODB_MESSAGES_DIR, "from_marker", f"response_{int(time.time())}.json")
    try:
        with open(response_file, 'w') as f:
            json.dump(response, f, indent=2)
    except Exception as e:
        typer.echo(f"Error saving response: {e}")
        raise typer.Exit(code=1)
    
    typer.echo(f"Response saved to: {response_file}")
    
    # Try to notify ArangoDB
    try:
        subprocess.run(
            [
                "cd", ARANGODB_PATH, "&&", 
                "python", "src/arangodb/cli/agent_commands.py", "process-message", response_file
            ],
            shell=True,
            check=False
        )
        typer.echo("Notified ArangoDB of response")
    except Exception as e:
        typer.echo(f"Warning: Failed to notify ArangoDB: {e}")
    
    typer.echo("Message processed successfully")


@app.command("send-message")
def send_message(
    content: str = typer.Argument(..., help="Message content"),
    message_type: str = typer.Option("request", help="Message type (request/response/notification)")
):
    """
    Send a message to ArangoDB module.
    
    This command creates a message file for ArangoDB and triggers
    the ArangoDB module to process it.
    """
    # Validate message type
    valid_types = ["request", "response", "notification"]
    if message_type not in valid_types:
        typer.echo(f"Error: Invalid message type: {message_type}. Valid types: {', '.join(valid_types)}")
        raise typer.Exit(code=1)
    
    # Create message
    message = {
        "source": "marker",
        "target": "arangodb",
        "type": message_type,
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "metadata": {
            "version": "1.0"
        }
    }
    
    # Save message to ArangoDB's incoming directory
    message_file = os.path.join(ARANGODB_MESSAGES_DIR, "from_marker", f"message_{int(time.time())}.json")
    try:
        with open(message_file, 'w') as f:
            json.dump(message, f, indent=2)
    except Exception as e:
        typer.echo(f"Error saving message file: {e}")
        raise typer.Exit(code=1)
    
    typer.echo(f"Message saved to: {message_file}")
    
    # Attempt to trigger ArangoDB's process-message command
    try:
        subprocess.run(
            [
                "cd", ARANGODB_PATH, "&&",
                "python", "src/arangodb/cli/agent_commands.py", "process-message", message_file
            ],
            shell=True,
            check=False
        )
        typer.echo("Notified ArangoDB of message")
    except Exception as e:
        typer.echo(f"Warning: Failed to notify ArangoDB: {e}")
    
    typer.echo("Message sent successfully")


if __name__ == "__main__":
    app()
