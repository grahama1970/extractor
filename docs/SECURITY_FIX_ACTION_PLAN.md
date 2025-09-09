# Security Fix Action Plan: Practical Approach

## Overview
Based on the security scan, we found 67 shell injection vulnerabilities and 3 eval() vulnerabilities. This plan focuses on fixing ONLY the real security issues without over-engineering.

## Quick Wins (1 hour)

### 1. Fix eval() usage (3 files, 15 minutes)
These are critical and easy to fix:

```python
# File: src/extractor/core/services/litellm.py (line 157)
# File: src/extractor/core/llm_call/litellm_integration.py (line 73)  
# File: src/extractor/core/llm_call/cli/app.py (line 54)

# Change from:
params[key.strip()] = eval(value.strip())

# To:
import ast
params[key.strip()] = ast.literal_eval(value.strip())
```

### 2. Fix Critical shell=True in main files (30 minutes)
Focus on user-facing code first:

```python
# implement_jq_based_extractor.py
# Change from:
cmd = f"jq '{jq_query}' {json_file}"
subprocess.run(cmd, shell=True)

# To:
subprocess.run(['jq', jq_query, json_file])
```

### 3. Add path validator utility (15 minutes)
Already created at `src/extractor/core/utils/path_validator.py`

## Medium Priority (1-2 hours)

### Fix Claude processors shell=True
These files process user PDFs and need fixing:
- `src/extractor/core/processors/claude_*.py` (5 files)
- `src/extractor/core/utils/pdf_opener.py`

Pattern to fix:
```python
# Change from:
subprocess.Popen(f"claude {options} {file}", shell=True)

# To:
subprocess.Popen(['claude'] + options.split() + [file])
```

## Low Priority (Optional)

### Fix test/prompt files
- Files in `src/extractor/prompts/` - These are documentation, not production code
- Test files - Not user-facing

## What NOT to Fix

1. **DO NOT** add SSRF protection - Not a web service
2. **DO NOT** add rate limiting - Local tool
3. **DO NOT** add CSP headers - Not a web app
4. **DO NOT** add thread locks - Sequential processing
5. **DO NOT** add crypto signing - Over-engineering
6. **DO NOT** fix files in tmp/ or docs/ - Not executable

## Simple Fix Script

```bash
#!/bin/bash
# Quick fixes for critical vulnerabilities

# Fix eval() usage
echo "Fixing eval() vulnerabilities..."
sed -i 's/eval(value\.strip())/ast.literal_eval(value.strip())/g' \
  src/extractor/core/services/litellm.py \
  src/extractor/core/llm_call/litellm_integration.py \
  src/extractor/core/llm_call/cli/app.py

# Add ast import if needed
for f in src/extractor/core/services/litellm.py \
         src/extractor/core/llm_call/litellm_integration.py \
         src/extractor/core/llm_call/cli/app.py; do
  if ! grep -q "import ast" "$f"; then
    sed -i '1a import ast' "$f"
  fi
done

echo "✅ Critical fixes applied!"
```

## Verification

After fixes, verify with:
```python
# Test eval fix
python -c "from src.extractor.core.services.litellm import *"

# Test subprocess fix  
python implement_jq_based_extractor.py test.json
```

## Time Estimate

- Critical fixes: 1 hour
- All production code: 3 hours
- Everything (including tests): 5 hours

**Recommendation:** Do critical fixes only (1 hour) unless security audit requires more.

## Remember

- This is a document processor, not a banking app
- Working code > Perfect code
- Fix real vulnerabilities, ignore enterprise patterns
- 80/20 rule: Fix the 20% that gives 80% security improvement