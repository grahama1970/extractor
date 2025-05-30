Creating test app...")
app = typer.Typer(name="test-marker")

@app.command()
def hello(name: str = typer.Argument("World")):
    """Say hello to someone."""
    print(f"Hello {name}!")

@app.command()
def extract_simple(pdf_path: str = typer.Argument(...)):
    """Simple extraction test."""
    print(f"Would extract: {pdf_path}")

# Add MCP commands
print("Adding MCP commands...")
add_slash_mcp_commands(app)

# List commands
print("\nRegistered commands:")
for cmd in app.registered_commands:
    name = cmd.name or cmd.callback.__name__
    print(f"  - {name}")

print("\n✓ MCP functionality test passed!")
print("\nTo generate MCP config, run:")
print("  python test_mcp_functionality.py generate-mcp-config")
print("\nTo generate Claude commands, run:")
print("  python test_mcp_functionality.py generate-claude")