"""
Module: module_query_demo.py
Description: Implementation of module query demo functionality

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

===== Querying Any Module with Generic Function =====")
    
    # Example: Query ArangoDB about its name and version
    arangodb_path = "."
    result = query_module(
        prompt="What is the name and version of this project?",
        module_path=arangodb_path,
        module_name="ArangoDB"
    )
    
    print("\nGeneric Query Result:")
    print(json.dumps(result, indent=2))
    
    return result


def demo_get_arangodb_export_format_sync():
    """Demonstrate querying ArangoDB for export format synchronously."""
    print("\n===== Querying ArangoDB for PDF Export Format (Synchronous) =====")
    
    # Get the export format for PDF documents
    export_format = get_export_format(document_type="pdf", background=False)
    
    print("\nExport Format Response:")
    print(json.dumps(export_format, indent=2))
    
    return export_format


def demo_get_arangodb_export_format_async():
    """Demonstrate querying ArangoDB for export format asynchronously."""
    print("\n===== Querying ArangoDB for PDF Export Format (Asynchronous) =====")
    
    # Start the background query
    query_response = get_export_format(document_type="pdf", background=True)
    query_id = query_response.get("query_id")
    
    print("\nStarted background query with ID:", query_id)
    print("Initial response:", json.dumps(query_response, indent=2))
    
    # Poll for results
    print("\nPolling for results...")
    max_attempts = 10
    attempts = 0
    
    while attempts < max_attempts:
        attempts += 1
        print(f"\nCheck attempt {attempts}...")
        
        # Check status
        status_response = get_response_status(query_id)
        status = status_response.get("status", "unknown")
        
        print(f"Status: {status}")
        
        if status == "completed":
            print("\nQuery completed! Result:")
            print(json.dumps(status_response.get("response", {}), indent=2))
            return status_response.get("response", {})
        elif status == "error":
            print("\nQuery failed with error:", status_response.get("error", "Unknown error"))
            return status_response
        
        # Wait before next check
        print("Waiting 3 seconds before next check...")
        time.sleep(3)
    
    print("\nReached maximum polling attempts. Query may still be running.")
    print("You can check the status later with:")
    print(f"  get_response_status('{query_id}')")
    
    return query_response


def demo_update_arangodb_format():
    """Demonstrate requesting ArangoDB to update its export format."""
    print("\n===== Requesting ArangoDB to Update Export Format =====")
    
    # Create format update request
    format_updates = {
        "document_type": "pdf",
        "field_changes": {
            "rename": {
                "question_type": "type"  # Rename question_type to type
            },
            "add": {
                "source": "string",  # Add source field
                "confidence": "float"  # Add confidence field
            }
        }
    }
    
    print("\nRequested Updates:")
    print(json.dumps(format_updates, indent=2))
    
    # Custom system prompt for this specific task
    system_prompt = """
    You are an ArangoDB developer with deep knowledge of the codebase.
    Your task is to assess whether proposed format changes are feasible
    and identify the exact files that would need to be modified.
    
    Be specific about:
    - Which files would need to change
    - How difficult the changes would be
    - Any potential side effects
    
    Structure your response as JSON with detailed implementation steps.
    """
    
    # Request the update with a custom system prompt
    update_result = update_export_format(
        format_updates,
        background=False  # Run synchronously for this demo
    )
    
    print("\nUpdate Assessment Result:")
    print(json.dumps(update_result, indent=2))
    
    return update_result


def main():
    """Run the demonstration."""
    print("Starting Module Query Demo")
    print("========================")
    
    # Step 1: Demonstrate generic module query
    generic_result = demo_query_any_module()
    
    # Step 2: Demonstrate synchronous query
    sync_result = demo_get_arangodb_export_format_sync()
    
    # Step 3: Demonstrate asynchronous query with polling
    async_result = demo_get_arangodb_export_format_async()
    
    # Step 4: Demonstrate format update
    update_result = demo_update_arangodb_format()
    
    print("\n===== Demo Completed Successfully =====")
    print("Response storage is in ~/.claude_responses/")
    print("You can retrieve past responses using the query ID")


if __name__ == "__main__":
    main()