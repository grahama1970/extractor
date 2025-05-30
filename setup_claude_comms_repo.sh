#!/bin/bash
# Script to set up the claude_comms repository

set -e

# Navigate to the claude_comms directory
cd /home/graham/workspace/experiments/claude_comms

echo "Setting up Git repository in $(pwd)..."

# Initialize Git repository
git init

# Remove marker_comms directory as it's no longer needed
rm -rf src/marker_comms

# Update pyproject.toml
echo "Updating pyproject.toml..."
sed -i 's/marker-comms/claude-comms/g' pyproject.toml
sed -i 's/github.com\/grahama1970\/marker/github.com\/grahama1970\/claude-comms/g' pyproject.toml
sed -i 's/github.com\/grahama1970\/marker\/tree\/master\/comms/github.com\/grahama1970\/claude-comms/g' pyproject.toml

# Create app.py in cli directory
echo "Creating CLI app..."
cat > src/claude_comms/cli/app.py << 'EOF'
#!/usr/bin/env python3
"""
Command-line interface for claude-comms.

This module provides a CLI for interacting with the claude-comms system.
"""

import sys
import argparse
import json
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..core.communicator import create_communicator
from ..core.conversation_store import ConversationStore
from ..settings import Settings


def main():
    """Main entry point for claude-comms CLI."""
    parser = argparse.ArgumentParser(description="Claude Communications Tool")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Send command
    send_parser = subparsers.add_parser("send", help="Send a message to another module")
    send_parser.add_argument("prompt", help="The message to send")
    send_parser.add_argument("--module", "-m", required=True, help="Target module")
    send_parser.add_argument("--path", "-p", help="Path to the module")
    send_parser.add_argument("--thread", "-t", help="Thread ID for continuing conversations")
    send_parser.add_argument("--background", "-b", action="store_true", help="Run in background")

    # List command
    list_parser = subparsers.add_parser("list", help="List conversations")
    list_parser.add_argument("--module", "-m", help="Filter by module")
    list_parser.add_argument("--limit", "-l", type=int, default=10, help="Number of conversations to show")

    # Thread command
    thread_parser = subparsers.add_parser("thread", help="View a conversation thread")
    thread_parser.add_argument("thread_id", help="Thread ID to view")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search for messages")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--module", "-m", help="Filter by module")
    search_parser.add_argument("--limit", "-l", type=int, default=10, help="Number of results to show")

    # Config command
    config_parser = subparsers.add_parser("config", help="Configure claude-comms")
    config_parser.add_argument("--list-modules", action="store_true", help="List configured modules")
    config_parser.add_argument("--add-module", help="Add module path (format: name=path)")
    config_parser.add_argument("--save", action="store_true", help="Save configuration changes")

    args = parser.parse_args()

    if args.command == "send":
        cmd_send(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "thread":
        cmd_thread(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "config":
        cmd_config(args)
    else:
        parser.print_help()


def cmd_send(args):
    """Send a message to another module."""
    communicator = create_communicator("cli")
    
    response = communicator.send_message(
        prompt=args.prompt,
        target_module=args.module,
        target_path=args.path,
        thread_id=args.thread,
        background=args.background
    )
    
    if args.background:
        print(f"Message sent in background. Query ID: {response.get('query_id')}")
    else:
        print(json.dumps(response, indent=2))


def cmd_list(args):
    """List conversations."""
    store = ConversationStore()
    threads = store.list_threads(module=args.module, limit=args.limit)
    
    if not threads:
        print("No conversations found.")
        return
    
    print(f"Found {len(threads)} conversation(s):")
    for thread in threads:
        print(f"- {thread['thread_id']}: {thread.get('title', 'Untitled')} ({len(thread.get('messages', []))} messages)")


def cmd_thread(args):
    """View a conversation thread."""
    store = ConversationStore()
    thread = store.get_thread(args.thread_id)
    
    if not thread:
        print(f"Thread {args.thread_id} not found.")
        return
    
    print(f"Thread: {thread.get('title', 'Untitled')}")
    print(f"ID: {thread['thread_id']}")
    print(f"Modules: {', '.join(thread.get('modules', []))}")
    print(f"Created: {thread.get('created_at', 'Unknown')}")
    print("\nMessages:")
    
    for i, msg in enumerate(thread.get('messages', [])):
        print(f"\n[{i+1}] {msg.get('module_name', 'Unknown')} ({msg.get('timestamp', 'Unknown')})")
        print("-" * 80)
        print(msg.get('content', ''))
        print("-" * 80)


def cmd_search(args):
    """Search for messages."""
    store = ConversationStore()
    results = store.search_messages(query=args.query, module=args.module, limit=args.limit)
    
    if not results:
        print("No messages found.")
        return
    
    print(f"Found {len(results)} message(s):")
    for result in results:
        print(f"\nThread: {result['thread_id']}")
        print(f"Module: {result.get('module_name', 'Unknown')}")
        print(f"Timestamp: {result.get('timestamp', 'Unknown')}")
        print("-" * 80)
        print(result.get('content', '')[:200] + ("..." if len(result.get('content', '')) > 200 else ""))
        print("-" * 80)


def cmd_config(args):
    """Configure claude-comms."""
    settings = Settings()
    
    if args.list_modules:
        modules = settings.get_module_paths()
        if not modules:
            print("No modules configured.")
        else:
            print("Configured modules:")
            for name, path in modules.items():
                print(f"- {name}: {path}")
    
    if args.add_module:
        try:
            name, path = args.add_module.split("=", 1)
            modules = settings.get_module_paths() or {}
            modules[name] = path
            settings.set("module_paths", modules)
            print(f"Added module {name} with path {path}")
        except ValueError:
            print("Error: Module specification must be in the format 'name=path'")
    
    if args.save:
        settings.save()
        print("Configuration saved.")


if __name__ == "__main__":
    main()
EOF

# Create a better README.md
echo "Creating README.md..."
cat > README.md << 'EOF'
# claude-comms

A modular system for inter-module communication using Claude.

## Overview

The claude-comms package enables:
- Sending queries from one module to another using Claude
- Maintaining threaded conversations between modules
- Using customized system prompts for domain-specific expertise
- Running queries in the background with response storage
- Validating data using shared corpus validation
- Persisting conversation history with TinyDB

## Installation

There are several ways to install the claude-comms package:

### Quick Installation

```bash
# Clone the repository
git clone https://github.com/grahama1970/claude-comms.git
cd claude-comms

# Run the installation script
./install.sh
```

### Manual Installation

```bash
# Install with UV in development mode
uv pip install -e .
```

### Dependencies

- Python 3.10+
- TinyDB (required for conversation storage)
- Loguru (required for logging)
- Claude CLI tool installed and available in PATH

## Configuration

The claude-comms system is designed to communicate with any module at any path. You can configure global settings through:

1. Environment variables:
```bash
export CLAUDE_COMMS_STORAGE_DIR="/path/to/storage"
export CLAUDE_COMMS_LOG_LEVEL="DEBUG"
export CLAUDE_COMMS_MODULE_PATHS="module1=/path/to/module1,module2=/path/to/module2"
```

2. Config file:
```bash
# Located at ~/.config/claude_comms/config.json
{
  "storage_dir": "/path/to/storage",
  "log_level": "DEBUG",
  "module_paths": {
    "marker": "/path/to/marker",
    "arangodb": "/path/to/arangodb",
    "custom_module": "/path/to/custom_module"
  }
}
```

3. Command-line:
```bash
# Configure module paths
claude-comms config --add-module "custom_module=/path/to/custom_module" --save

# Set storage directory
claude-comms config --set "storage_dir=/path/to/storage" --save

# List all configuration
claude-comms config --list
```

The configuration is global, allowing you to communicate with different modules from any project using the same Claude instance.

## Usage

### Python API

```python
from claude_comms import create_communicator

# Create a communicator for your module
communicator = create_communicator("MyModule")

# Or use the pre-configured communicators
from claude_comms import get_communicator

# Get communicators for any configured modules
marker_communicator = get_communicator("marker")
arangodb_communicator = get_communicator("arangodb")
custom_communicator = get_communicator("custom_module")

# Send a message to another module (path is taken from config if configured)
response = marker_communicator.send_message(
    prompt="What is the format of document exports?",
    target_module="arangodb"
)

# Or specify a path directly for any module
response = communicator.send_message(
    prompt="Analyze this module structure",
    target_module="any_module",
    target_path="/path/to/any/module"
)

# Get the thread ID
thread_id = response["thread_id"]

# Continue the conversation
response = marker_communicator.send_message(
    prompt="Can you provide more details about the 'metadata' field?",
    target_module="arangodb",
    thread_id=thread_id
)

# Send a message with a custom system prompt
response = marker_communicator.send_message(
    prompt="Analyze the performance of this function",
    target_module="arangodb",
    system_prompt="You are a performance optimization expert. Focus on identifying bottlenecks in database queries."
)

# List all conversations with any module
conversations = marker_communicator.list_conversations(
    target_module="arangodb",
    limit=10
)

# Retrieve a specific conversation
conversation = marker_communicator.get_conversation(thread_id)

# Search for messages containing a query
messages = marker_communicator.search_messages(
    query="exports",
    target_module="arangodb"
)
```

### Command-Line Interface

The package installs a `claude-comms` command-line tool for communicating with any module from the terminal:

```bash
# Show help
claude-comms --help

# Send a message to any configured module
claude-comms send "What is the format of document exports?" --module arangodb

# Send a message to any module by path
claude-comms send "Analyze this codebase" --module custom_module --path /path/to/custom/module

# Continue a conversation
claude-comms send "Tell me more about metadata" --module arangodb --thread <thread_id>

# Run a query in the background
claude-comms send "Generate a complex AQL query" --module arangodb --background

# Check background query status
claude-comms status <query_id>

# List all conversations
claude-comms list

# List conversations with a specific module
claude-comms list --module arangodb

# View a conversation thread
claude-comms thread <thread_id>

# Search for messages
claude-comms search "exports"

# Filter search by module
claude-comms search "exports" --module arangodb

# Configure module paths
claude-comms config --add-module "custom_module=/path/to/custom/module" --save

# List configured modules
claude-comms config --list-modules
```

## Integration with Projects

To use claude-comms in your project, add it to your dependencies in pyproject.toml:

```toml
[project]
# ... existing configuration
dependencies = [
    # ... existing dependencies
    "claude-comms>=0.1.0",
]
```

Then in your code:

```python
from claude_comms import create_communicator

# Create a communicator for your module
communicator = create_communicator("my_module")

# Send a message to another module
response = communicator.send_message(
    prompt="Analyze this function",
    target_module="other_module",
    target_path="/path/to/other/module"
)

print(response["content"])
```

## Resources

- [Claude Documentation](https://docs.anthropic.com/claude/docs)
- [System Prompts Guide](https://docs.anthropic.com/claude/docs/system-prompts)
- [Claude Code Documentation](https://docs.anthropic.com/en/docs/claude-code)
- [TinyDB Documentation](https://tinydb.readthedocs.io/)
EOF

# Add gitignore
echo "Creating .gitignore..."
cat > .gitignore << 'EOF'
# Python package files
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Distribution / packaging
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# IDE files
.idea/
.vscode/
*.swp
*.swo

# Project-specific
.cache/
.coverage
htmlcov/
.pytest_cache/
.tox/
.nox/
coverage.xml
*.cover
.hypothesis/
.DS_Store

# Project conversations 
conversations/*.json
conversations/*.db
EOF

# Add GitHub-specific files
echo "Creating GitHub workflow files..."
mkdir -p .github/workflows

cat > .github/workflows/python-package.yml << 'EOF'
name: Python package

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11"]

    steps:
    - uses: actions/checkout@v3
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install hatch
        pip install -e ".[dev]"
    - name: Test with pytest
      run: |
        pytest
EOF

# Create a GitHub repo
# (This assumes you have gh CLI installed and authenticated)
echo "Creating GitHub repository (requires gh CLI)..."

if command -v gh &> /dev/null; then
    echo "Found GitHub CLI, creating repository..."
    gh repo create grahama1970/claude-comms \
      --description "Inter-module communication system for Python projects using Claude" \
      --public \
      || echo "Warning: Could not create GitHub repository. You can create it manually later."
else
    echo "GitHub CLI not found. Please create the repository manually at https://github.com/new"
fi

# Add, commit, and push
echo "Adding and committing files..."
git add .
git commit -m "Initial commit: claude-comms package

This commit establishes the claude-comms package, a standalone module for
inter-module communication using Claude. The package provides APIs for
sending queries between different codebases, maintaining conversation
history, and performing validations."

# If repo was created, push to it
if command -v gh &> /dev/null; then
    echo "Pushing to GitHub..."
    git remote add origin https://github.com/grahama1970/claude-comms.git
    git branch -M main
    git push -u origin main || echo "Warning: Could not push to GitHub. You can push manually later."
else
    echo "Please push manually once you've created the GitHub repository."
fi

echo ""
echo "================================"
echo "Setup complete! Next steps:"
echo "1. Open the project in VSCode: code /home/graham/workspace/experiments/claude_comms"
echo "2. Review and finalize any changes needed"
echo "3. If not already pushed, push to GitHub manually"
echo "================================"