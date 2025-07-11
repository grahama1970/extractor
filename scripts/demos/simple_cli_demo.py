"""
Module: simple_cli_demo.py
Description: Command line interface functionality

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

" + json.dumps(response, indent=2)
    
    # Format status
    status = response.get("status", "unknown")
    if status == "pending":
        status_str = f"\033[93mStatus: {status}\033[0m"
    elif status == "completed":
        status_str = f"\033[92mStatus: {status}\033[0m"
    elif status == "error":
        status_str = f"\033[91mStatus: {status}\033[0m"
    else:
        status_str = f"Status: {status}"
    
    # Format response
    return f"{status_str}\n{json.dumps(response, indent=2)}"


def query_command(args):
    """Handle query command."""
    # Get module path 
    if args.arangodb:
        module_path = args.arangodb_path
        module_name = "ArangoDB"
    else:
        module_path = args.module_path
        module_name = args.module_name or Path(module_path).name
    
    # Read system prompt from file if provided
    system_prompt = args.system_prompt
    if args.system_prompt_file:
        with open(args.system_prompt_file, "r") as f:
            system_prompt = f.read()
    
    # Execute query
    if args.arangodb:
        response = query_arangodb(
            prompt=args.prompt,
            arangodb_path=module_path,
            system_prompt=system_prompt,
            background=args.background
        )
    else:
        response = query_module(
            prompt=args.prompt,
            module_path=module_path,
            system_prompt=system_prompt,
            module_name=module_name,
            background=args.background
        )
    
    # Format and print response
    print(format_response(response, colorize=not args.no_color))
    
    # If background mode, show how to check status
    if args.background and response.get("query_id"):
        print(f"\nTo check the status:")
        print(f"  {sys.argv[0]} status {response['query_id']}")


def status_command(args):
    """Handle status command."""
    response = get_response_status(args.query_id)
    print(format_response(response, colorize=not args.no_color))


def list_command(args):
    """Handle list command."""
    responses = response_storage.list_responses(
        module_name=args.module_name,
        limit=args.limit
    )
    
    if not responses:
        print("No responses found")
        return
    
    print(f"Found {len(responses)} responses:")
    for i, response in enumerate(responses, 1):
        query_id = response.get("id")
        timestamp = response.get("timestamp", "unknown").split("T")[0]
        module = response.get("module", "unknown")
        print(f"{i}. {query_id} - {module} ({timestamp})")
        
        # Show details if requested
        if args.details:
            try:
                full_response = response_storage.get_response(query_id)
                prompt = full_response.get("metadata", {}).get("prompt", "No prompt")
                print(f"   Prompt: {prompt[:50]}...")
            except Exception as e:
                print(f"   [Could not load details: {e}]")
        
    print("\nTo check a specific response:")
    print(f"  {sys.argv[0]} status <query_id>")


def city_check_command(args):
    """Check if a city is in the allowed list."""
    # Check allowed_cities.txt
    cities_file = Path("allowed_cities.txt")
    if not cities_file.exists():
        print("❌ allowed_cities.txt not found")
        print("Run the setup command from arangodb_integration_demo.py first")
        return False
    
    # Load allowed cities
    with open(cities_file, "r") as f:
        allowed_cities = {city.strip() for city in f if city.strip()}
    
    # Check if city is in allowed list
    city = args.city
    is_valid = city in allowed_cities
    
    if is_valid:
        print(f"✅ '{city}' is in the allowed cities list")
    else:
        print(f"❌ '{city}' is NOT in the allowed cities list")
        print(f"Allowed cities include: {', '.join(list(allowed_cities)[:5])}...")
    
    return is_valid


def aql_check_command(args):
    """Check if an AQL query is valid."""
    # Prompt ArangoDB for AQL validation
    prompt = f"""
    Please validate the following AQL query and tell me if it's syntactically correct:
    
    ```
    {args.query}
    ```
    
    Return the result as a JSON object with the following structure:
    {{
      "valid": true/false,
      "error": "error message if any",
      "suggestions": ["suggestion1", "suggestion2"]
    }}
    """
    
    # Use background mode based on args
    response = query_arangodb(
        prompt=prompt,
        background=args.background
    )
    
    # Print the response
    print(format_response(response, colorize=not args.no_color))


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Module Communication CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Global arguments
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # Query command
    query_parser = subparsers.add_parser("query", help="Query a module")
    query_parser.add_argument("prompt", help="The prompt to send")
    module_group = query_parser.add_mutually_exclusive_group(required=True)
    module_group.add_argument("--module-path", help="Path to the module directory")
    module_group.add_argument("--arangodb", action="store_true", help="Query ArangoDB")
    query_parser.add_argument("--arangodb-path", default=".", help="Path to ArangoDB (default: %(default)s)")
    query_parser.add_argument("--module-name", help="Name of the module (defaults to directory name)")
    query_parser.add_argument("--system-prompt", help="Custom system prompt")
    query_parser.add_argument("--system-prompt-file", help="File containing the system prompt")
    query_parser.add_argument("--background", "-b", action="store_true", help="Run in background mode")
    query_parser.set_defaults(func=query_command)
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check status of a query")
    status_parser.add_argument("query_id", help="The query ID to check")
    status_parser.set_defaults(func=status_command)
    
    # List command
    list_parser = subparsers.add_parser("list", help="List saved responses")
    list_parser.add_argument("--module-name", help="Filter by module name")
    list_parser.add_argument("--limit", type=int, default=10, help="Maximum number of responses to list (default: %(default)s)")
    list_parser.add_argument("--details", "-d", action="store_true", help="Show response details")
    list_parser.set_defaults(func=list_command)
    
    # City validation command
    city_parser = subparsers.add_parser("check-city", help="Check if a city is allowed")
    city_parser.add_argument("city", help="The city to check")
    city_parser.set_defaults(func=city_check_command)
    
    # AQL validation command
    aql_parser = subparsers.add_parser("check-aql", help="Check if an AQL query is valid")
    aql_parser.add_argument("query", help="The AQL query to validate")
    aql_parser.add_argument("--background", "-b", action="store_true", help="Run in background mode")
    aql_parser.set_defaults(func=aql_check_command)
    
    # Parse args
    args = parser.parse_args()
    
    # Handle default command
    if not args.command:
        parser.print_help()
        return 0
    
    # Execute command
    try:
        result = args.func(args)
        return 0 if result is None or result else 1
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 1
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())