# Script Improvements: Retry Logic and Embedded Prompts

## 1. Added Tenacity for Retry Logic

Added `tenacity` library for robust retry handling with exponential backoff on API calls.

### Implementation Details

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type((
        ConnectionError,
        TimeoutError,
        litellm.APIConnectionError,
        litellm.ServiceUnavailableError,
        litellm.InternalServerError,
        litellm.RateLimitError
    )),
    before_sleep=lambda retry_state: logger.warning(
        f"Retrying AI code review (attempt {retry_state.attempt_number}/3) after error: "
        f"{retry_state.outcome.exception() if retry_state.outcome else 'Unknown error'}"
    )
)
async def perform_ai_code_review(...)
```

### Benefits
- **Automatic retry** on network errors (up to 3 attempts)
- **Exponential backoff** prevents overwhelming the API (4s, 8s, 16s, etc.)
- **Smart retry logic** - only retries on recoverable errors, not auth errors
- **Better reliability** for production environments
- **User visibility** with warning logs on retry attempts

## 2. Support for Embedded Prompts in Config

The configuration now supports having the code review prompt directly in the JSON config file, making it more self-contained.

### Old Format (Still Supported)
```json
{
    "code_review_prompt_file": "prompts/code_review_prompt.md",
    "files_to_review": [...]
}
```

### New Format (Recommended)
```json
{
    "code_review_prompt": "Your comprehensive code review prompt here...",
    "files_to_review": [...]
}
```

### Benefits
- **Self-contained configuration** - everything in one file
- **Easier deployment** - no separate prompt files to manage
- **Better version control** - prompt changes tracked with config
- **Backward compatible** - old format still works

## 3. Fixed Model Names

Updated default model names to use correct Moonshot model identifiers:
- Changed from `moonshot/kimi-k2` to `moonshot/moonshot-v1-32k`
- Available models:
  - `moonshot/moonshot-v1-8k` (8K context)
  - `moonshot/moonshot-v1-32k` (32K context - recommended)
  - `moonshot/moonshot-v1-128k` (128K context)

## Usage Example

```bash
# With embedded prompt config
python generate_code_review_bundle.py generate_code_config_embedded.json \
  --ai-review --model moonshot/moonshot-v1-32k

# Output
✅ Bundle successfully generated to 'stdout'.
   Files processed: 5/7
✅ AI review saved to: /path/to/ai_code_review_20250723_120000.md
   Tokens used: 25694
   Cost: $0.0257
```

## Installation

```bash
# Add tenacity dependency
uv add tenacity
```

## Configuration Validation

The script now validates that configs have either:
- `code_review_prompt_file` (for backward compatibility)
- `code_review_prompt` (for self-contained configs)

This makes the system more flexible while maintaining compatibility with existing configurations.