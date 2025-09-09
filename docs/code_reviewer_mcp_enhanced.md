# Code-Reviewer MCP Enhancement

## Enhancement Summary

The code-reviewer MCP has been enhanced to return the actual review content in the JSON response, making it much more useful for programmatic access.

## Changes Made

1. **Enhanced MCP Adapter** (`/home/graham/.claude/mcp/code-reviewer/mcp_adapter.py`)
   - Now includes `review_content` in the response JSON
   - Also includes `bundle_content` for complete access
   - Maintains backward compatibility with all existing functionality

## Before (Original Behavior)
```json
{
  "status": "success",
  "bundle_path": "/path/to/bundle.md",
  "review_path": "/path/to/review.md",
  "files_processed": 1,
  "total_size": 12345
}
```
Returns `null` through MCP, requiring you to read the files separately.

## After (Enhanced Behavior)
```json
{
  "status": "success",
  "bundle_path": "/path/to/bundle.md",
  "review_path": "/path/to/review.md",
  "files_processed": 1,
  "total_size": 12345,
  "review_content": "---\n### File: `src/file.py`\n\n**Overall Assessment:** ...",
  "bundle_content": "# Code Review Bundle\n\n..."
}
```
Returns the complete review content directly in the JSON response.

## Benefits

1. **Direct Access** - No need to read files separately
2. **Better Integration** - Can process review results programmatically
3. **Cleaner Workflow** - Single call gets everything you need
4. **Backward Compatible** - Old behavior still works, just with extra fields

## Usage

After reloading Claude to pick up the enhanced adapter:

```python
result = await mcp__code-reviewer__review_cli(
    config_path="/path/to/config.json",
    model="moonshot/kimi-k2-turbo-preview",
    include_git_info="false"
)

# Now you can access the review directly!
review_content = result['review_content']
print(review_content)
```

## Technical Details

The enhancement works by:
1. Intercepting the `review_cli` method
2. Running the original review process
3. Reading the generated files
4. Including their content in the response

This maintains all original functionality while providing a much better developer experience.