# PATH and Claude Batch Processing Lessons Learned

## Overview
This document captures critical lessons learned while implementing the PDF annotation analysis system, specifically around subprocess execution and Claude batch processing.

## Lesson 1: The PATH Problem

### Symptom
```
Error: spawn ps ENOENT
```

### Root Cause
Claude Code's environment has a minimal PATH that doesn't include standard system directories like `/usr/bin` and `/bin`. When Node.js (used by Claude CLI) attempts to spawn child processes, it cannot find basic system commands like `ps`, `kill`, `which`, etc.

### Solution
Always use a comprehensive PATH when spawning subprocesses:

```python
def get_comprehensive_env():
    """Get environment with comprehensive PATH for subprocess calls."""
    env = os.environ.copy()
    
    # Include ALL system paths FIRST
    system_paths = [
        "/usr/bin",          # ps, kill, which, etc.
        "/bin",              # ls, cat, grep, etc.  
        "/usr/local/bin",    # locally installed
        "/sbin",             # system binaries
        "/usr/sbin",         # more system binaries
    ]
    
    # Then app-specific paths
    app_paths = [
        "/home/graham/.bun/bin",                         # Bun/Claude CLI
        "/home/graham/.nvm/versions/node/v20.11.1/bin", # Node.js
        "/home/graham/.local/bin",                       # User binaries
    ]
    
    # Combine paths - system first, then apps, then existing PATH
    all_paths = system_paths + app_paths + [env.get("PATH", "")]
    env["PATH"] = ":".join(filter(None, all_paths))
    env["BUN_INSTALL"] = "/home/graham/.bun"
    
    return env

# Use in subprocess calls
proc = await asyncio.create_subprocess_exec(
    *cmd,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,  
    env=get_comprehensive_env()  # Critical!
)
```

### Why This Happens
1. Claude Code runs in a minimal environment
2. Subprocesses inherit this limited PATH
3. Node.js needs `ps` to manage child processes
4. Error cascades: ps not found → process management fails → subprocess hangs

## Lesson 2: Claude Batch Processing Pattern

### Problem
When calling Claude via subprocess in async batch processing:
- Multiple concurrent calls via asyncio
- Each call needs proper environment setup
- Without proper stream handling, subprocesses deadlock at 64KB buffer limit

### The Buffer Deadlock Problem
Subprocess pipes have limited buffer size (typically 64KB). When the buffer fills and you're not actively reading, the subprocess blocks forever waiting for buffer space. This creates a deadlock if you're waiting for the process to complete before reading.

```python
# WRONG - This WILL deadlock:
proc = await asyncio.create_subprocess_exec(
    sys.executable, 'script.py',
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE
)
# If script.py outputs >64KB, it blocks waiting for buffer space!
# But we're waiting for it to complete = DEADLOCK
exit_code = await proc.wait()  # Hangs forever
```

### Complete Working Solution

```python
class ProductionClaudeService:
    """Production-ready Claude subprocess service with all fixes."""
    
    def __init__(self, batch_size: int = 10, timeout: int = 30):
        self.batch_size = batch_size
        self.timeout = timeout
        
        # CRITICAL: Comprehensive PATH setup
        self.env = self._get_comprehensive_env()
        self.claude_path = "/home/graham/.bun/bin/claude"
        
    def _get_comprehensive_env(self) -> dict:
        """Setup environment with ALL required paths."""
        env = os.environ.copy()
        
        # System paths MUST come first
        system_paths = [
            "/usr/bin",          # ps, kill, which
            "/bin",              # ls, cat, grep
            "/usr/local/bin",    # local installs
            "/sbin",             # system binaries
            "/usr/sbin",         # more system bins
        ]
        
        app_paths = [
            "/home/graham/.bun/bin",      # Claude CLI
            "/home/graham/.local/bin",    # User bins
        ]
        
        all_paths = system_paths + app_paths + [env.get("PATH", "")]
        env["PATH"] = ":".join(filter(None, all_paths))
        env["BUN_INSTALL"] = "/home/graham/.bun"
        
        return env
    
    async def _call_claude_with_draining(self, prompt: str) -> str:
        """Single Claude call with proper stream draining."""
        cmd = [self.claude_path, '-p', '--dangerously-skip-permissions']
        
        # Collect output
        output_lines = []
        error_lines = []
        
        async def _drain_stream(stream, collector):
            """Drain stream to prevent deadlock."""
            while True:
                line = await stream.readline()
                if not line:
                    break
                decoded = line.decode().strip()
                collector.append(decoded)
                logger.debug(f"Claude: {decoded}")
        
        # Start process
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self.env  # Use comprehensive env
        )
        
        # Start draining IMMEDIATELY
        drain_out = asyncio.create_task(_drain_stream(proc.stdout, output_lines))
        drain_err = asyncio.create_task(_drain_stream(proc.stderr, error_lines))
        
        # Send input and close
        proc.stdin.write(prompt.encode())
        await proc.stdin.drain()
        proc.stdin.close()
        
        # Wait with timeout
        try:
            await asyncio.wait_for(proc.wait(), timeout=self.timeout)
        except asyncio.TimeoutError:
            logger.error(f"Claude timeout after {self.timeout}s")
            proc.kill()
            await proc.wait()  # Ensure cleanup
            raise TimeoutError(f"Claude timeout: {self.timeout}s")
        
        # Ensure drains complete
        await asyncio.gather(drain_out, drain_err)
        
        # Check for errors
        if proc.returncode != 0:
            error_msg = "\n".join(error_lines)
            raise RuntimeError(f"Claude failed: {error_msg}")
        
        return "\n".join(output_lines)
    
    async def batch_process(self, items: List[Dict[str, Any]], 
                          prompt_template: str) -> List[Dict[str, Any]]:
        """Process items in controlled batches."""
        results = []
        total = len(items)
        
        for i in range(0, total, self.batch_size):
            batch = items[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (total + self.batch_size - 1) // self.batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches}")
            
            # Create tasks for batch
            tasks = []
            for item in batch:
                prompt = prompt_template.format(**item)
                task = self._call_claude_with_draining(prompt)
                tasks.append(task)
            
            # Execute with error handling
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for item, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Failed item {item.get('id', '?')}: {result}")
                    results.append({
                        **item,
                        "error": str(result),
                        "success": False
                    })
                else:
                    results.append({
                        **item,
                        "result": result,
                        "success": True
                    })
            
            # Brief pause between batches
            if i + self.batch_size < total:
                await asyncio.sleep(1)
        
        # Summary
        success_count = sum(1 for r in results if r.get("success"))
        logger.info(f"Batch processing complete: {success_count}/{total} successful")
        
        return results
```

### Critical Points

1. **Stream Draining**: MUST drain stdout/stderr immediately or subprocess deadlocks at 64KB
2. **Environment Setup**: Do ONCE in `__init__`, reuse for all calls
3. **Batch Control**: Limit concurrency to avoid overwhelming system
4. **Error Isolation**: Use `gather(return_exceptions=True)` to prevent cascade failures
5. **Timeout Protection**: Always use `wait_for` with reasonable timeout
6. **Proper Cleanup**: Always `kill()` then `wait()` on timeout

## Implementation in PDF Extraction Pipeline

The PDF annotation analysis system uses these patterns throughout:

1. **ClaudeSubprocessService**: Central service for all Claude calls
2. **Batch Processing**: Annotations processed in batches of 10
3. **Error Recovery**: Failed annotations don't stop the pipeline
4. **Progress Tracking**: Clear feedback during long operations

## Key Takeaways

1. **Never assume standard system commands are available** - Always provide comprehensive PATH
2. **Always drain subprocess streams immediately** - Prevents buffer deadlocks
3. **Batch processing needs careful orchestration** - Control concurrency, handle errors gracefully
4. **Environment setup is critical** - Do it once, reuse everywhere
5. **Test with large outputs** - Many subprocess issues only appear with >64KB output

## Testing Your Implementation

```python
# Test comprehensive PATH
async def test_path():
    env = get_comprehensive_env()
    proc = await asyncio.create_subprocess_exec(
        "which", "ps",
        stdout=asyncio.subprocess.PIPE,
        env=env
    )
    stdout, _ = await proc.communicate()
    assert proc.returncode == 0, "ps command not found!"
    print(f"✓ ps found at: {stdout.decode().strip()}")

# Test stream draining
async def test_large_output():
    # Generate >64KB output
    cmd = ["python", "-c", "print('x' * 100000)"]
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    # Must drain while running
    async def drain(stream):
        data = []
        while True:
            line = await stream.readline()
            if not line:
                break
            data.append(line)
        return b''.join(data)
    
    stdout_task = asyncio.create_task(drain(proc.stdout))
    stderr_task = asyncio.create_task(drain(proc.stderr))
    
    await proc.wait()
    stdout = await stdout_task
    
    assert len(stdout) > 64000, "Large output test failed"
    print(f"✓ Handled {len(stdout)} bytes without deadlock")
```

## Stored in Knowledge Architect

These lessons have been stored in the knowledge architect for future reference:
- Collection: `solutions`
- Tags: `PATH`, `subprocess`, `asyncio`, `batch`, `deadlock`
- Category: `environment_setup`, `async_patterns`

Access via:
```python
from knowledge_architect_worker import semantic_search

# Find PATH-related solutions
results = semantic_search(
    collection='solutions',
    query='spawn ps ENOENT PATH subprocess',
    text_field='problem',
    top_k=5
)
```