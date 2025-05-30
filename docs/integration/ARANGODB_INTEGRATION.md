# ArangoDB Integration Guide

This document provides guidance on integrating marker with ArangoDB for document storage, vector search, and knowledge graph capabilities.

## Overview

marker comes with a built-in integration with ArangoDB via the `claude-comms` module. This module allows seamless communication between marker and ArangoDB, enabling:

1. PDF document processing with marker
2. Vector embedding and storage in ArangoDB
3. Graph relationship mapping between document elements
4. Question-answering based on document content
5. Vector similarity search across document collections

## Setup and Configuration

### Prerequisites

- ArangoDB installed and running (version 3.8+)
- marker installed with the claude-comms module
- Claude CLI tool installed (for communication between modules)

### Configuration

1. Use the `claude-comms` CLI to configure the ArangoDB path:

```bash
claude-comms config --add-module "arangodb=/path/to/arangodb" --save
```

2. Or edit the config file directly at `~/.config/claude_comms/config.json`:

```json
{
  "arangodb_path": "/path/to/arangodb",
  "storage_dir": "~/.claude_comms/storage",
  "conversations_dir": "~/.claude_comms/conversations",
  "logs_dir": "~/.claude_comms/logs",
  "log_level": "INFO"
}
```

## Usage Examples

### Python API

```python
from claude_comms import get_communicator

# Get communicators for marker and ArangoDB
marker_communicator = get_communicator("marker")
arangodb_communicator = get_communicator("arangodb")

# Query ArangoDB about document format requirements
response = marker_communicator.send_message(
    prompt="What format and structure do you need for processing PDF exports?",
    target_module="arangodb"
)

# Process the response
requirements = response.get('response', {})
print(f"ArangoDB requirements: {requirements}")
```

### Command-Line Interface

```bash
# Query ArangoDB about document format
claude-comms send "What format and structure do you need for processing PDF exports?" --module arangodb

# Send a PDF processing result to ArangoDB
claude-comms send "Here's a processed PDF document: $(cat output.json)" --module arangodb
```

## Integration Workflow

A typical workflow for integrating marker with ArangoDB:

1. Process PDFs with marker to generate structured document data
2. Transform marker output to ArangoDB's expected format
3. Import the transformed data into ArangoDB
4. Create vector indexes for similarity search
5. Define graph relationships between document elements
6. Query the document collection using AQL

## Testing the Integration

Use the provided test script to verify the integration:

```bash
# Navigate to the comms directory
cd comms

# Run the analysis script
python analyze_arangodb_requirements.py
```

This script guides you through:
1. Understanding ArangoDB's requirements for document imports
2. Analyzing marker's output format against these requirements
3. Identifying any gaps or incompatibilities
4. Providing recommendations for aligning the formats

## Architecture

The integration between marker and ArangoDB uses a modular architecture:

1. **marker module**: Handles PDF processing and text extraction
2. **claude-comms module**: Facilitates communication between marker and ArangoDB
3. **ArangoDB module**: Provides database storage, vector search, and graph capabilities

Claude is used as the "bridge" between these modules, allowing them to understand each other's requirements and adapt accordingly.

## Advanced Usage

For advanced use cases, you can:

1. Customize the system prompts used for inter-module communication
2. Create specialized workflows for specific document types
3. Implement batch processing for large document collections
4. Configure custom vector embedding models and parameters
5. Design tailored graph schemas for specific document structures

## Resources

- [ArangoDB Documentation](https://www.arangodb.com/docs/)
- [marker Documentation](https://github.com/grahama1970/marker)
- [Claude Documentation](https://docs.anthropic.com/claude/docs)
- [Vector Search Guide](/comms/src/claude_comms/docs/ARANGODB_INTEGRATION.md)

## Troubleshooting

If you encounter issues:

1. Ensure the paths to marker and ArangoDB are correctly configured
2. Verify that the Claude CLI tool is properly installed and available
3. Check the logs in `~/.claude_comms/logs` for detailed error information
4. Ensure ArangoDB is running and accessible
5. Verify that the vector dimensions and formats match between marker and ArangoDB