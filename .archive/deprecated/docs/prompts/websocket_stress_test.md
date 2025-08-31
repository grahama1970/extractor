# WebSocket MCP Stress Test — websocket_stress_test.md

## 🔴 SELF-IMPROVEMENT RULES
This prompt MUST follow the self-improvement protocol:
1. Every failure updates metrics immediately
2. Every failure fixes the root cause
3. Every failure adds a recovery test
4. Every change updates evolution history

## 🎮 GAMIFICATION METRICS
- **Success**: 0
- **Failure**: 0
- **Total Executions**: 0
- **Last Updated**: 2025-06-25
- **Success Ratio**: N/A (need 10:1 to graduate)

## Evolution History
- v1: Initial implementation for cc_executor MCP WebSocket stress testing

## Purpose
Stress test the cc_executor MCP WebSocket service after refactoring, verifying all O3 fixes are working under load.

## Implementation

```python
#!/usr/bin/env python3
"""Stress test for cc_executor MCP WebSocket Service"""
import asyncio
import json
import time
import websockets
from datetime import datetime
import concurrent.futures
import statistics

class WebSocketStressTest:
    def __init__(self, base_url="ws://localhost:8003/ws/mcp"):
        self.base_url = base_url
        self.results = []
        
    async def single_session_test(self, session_id: str, command: str):
        """Test a single WebSocket session"""
        start_time = time.time()
        result = {
            "session_id": session_id,
            "command": command,
            "start_time": start_time,
            "success": False,
            "error": None,
            "duration": 0,
            "output_lines": 0
        }
        
        try:
            async with websockets.connect(self.base_url) as websocket:
                # Wait for connection confirmation
                conn_msg = await websocket.recv()
                conn_data = json.loads(conn_msg)
                
                # Send execute command
                execute_req = {
                    "jsonrpc": "2.0",
                    "method": "execute",
                    "params": {"command": command},
                    "id": 1
                }
                await websocket.send(json.dumps(execute_req))
                
                # Collect responses
                output_count = 0
                while True:
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=30)
                        data = json.loads(response)
                        
                        # Count output messages
                        if data.get("method") == "process.output":
                            output_count += 1
                        
                        # Check for completion
                        if data.get("method") == "process.completed":
                            result["success"] = True
                            result["exit_code"] = data["params"].get("exit_code", -1)
                            break
                            
                    except asyncio.TimeoutError:
                        result["error"] = "Timeout waiting for completion"
                        break
                        
                result["output_lines"] = output_count
                
        except Exception as e:
            result["error"] = str(e)
            
        result["duration"] = time.time() - start_time
        return result
        
    async def concurrent_sessions_test(self, num_sessions: int):
        """Test multiple concurrent sessions"""
        print(f"\n=== Testing {num_sessions} Concurrent Sessions ===")
        
        commands = [
            "echo 'Hello from session {}'".format(i),
            "python -c 'import time; print(\"Starting {}\"); time.sleep(2); print(\"Done {}\")".format(i, i),
            "for i in {1..10}; do echo 'Line {} from session {}'; sleep 0.1; done".format('$i', i),
            "ls -la | head -20",
            "python -c 'for i in range(100): print(f\"Fast output {}: {{i}}\")'.format(i)"
        ]
        
        tasks = []
        for i in range(num_sessions):
            command = commands[i % len(commands)]
            task = self.single_session_test(f"stress-{i}", command)
            tasks.append(task)
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        failed = len(results) - successful
        durations = [r["duration"] for r in results if isinstance(r, dict) and "duration" in r]
        
        print(f"✓ Successful: {successful}/{num_sessions}")
        print(f"✗ Failed: {failed}/{num_sessions}")
        if durations:
            print(f"Average duration: {statistics.mean(durations):.2f}s")
            print(f"Max duration: {max(durations):.2f}s")
            print(f"Min duration: {min(durations):.2f}s")
            
        return results
        
    async def process_control_test(self):
        """Test process control (PAUSE/RESUME/CANCEL)"""
        print("\n=== Testing Process Control ===")
        
        async with websockets.connect(self.base_url) as websocket:
            # Wait for connection
            await websocket.recv()
            
            # Start a long-running process
            execute_req = {
                "jsonrpc": "2.0",
                "method": "execute",
                "params": {"command": "python -c 'import time; [print(f\"Count {i}\", flush=True) or time.sleep(1) for i in range(30)]'"},
                "id": 1
            }
            await websocket.send(json.dumps(execute_req))
            
            # Wait for start confirmation
            while True:
                msg = await websocket.recv()
                data = json.loads(msg)
                if data.get("id") == 1:
                    print("✓ Process started")
                    break
                    
            # Let it run for 2 seconds
            await asyncio.sleep(2)
            
            # PAUSE
            pause_req = {
                "jsonrpc": "2.0",
                "method": "control",
                "params": {"type": "PAUSE"},
                "id": 2
            }
            await websocket.send(json.dumps(pause_req))
            pause_response = await websocket.recv()
            print("✓ Process paused")
            
            # Wait 2 seconds while paused
            await asyncio.sleep(2)
            
            # RESUME
            resume_req = {
                "jsonrpc": "2.0",
                "method": "control",
                "params": {"type": "RESUME"},
                "id": 3
            }
            await websocket.send(json.dumps(resume_req))
            resume_response = await websocket.recv()
            print("✓ Process resumed")
            
            # Let it run 2 more seconds
            await asyncio.sleep(2)
            
            # CANCEL
            cancel_req = {
                "jsonrpc": "2.0",
                "method": "control",
                "params": {"type": "CANCEL"},
                "id": 4
            }
            await websocket.send(json.dumps(cancel_req))
            cancel_response = await websocket.recv()
            print("✓ Process cancelled")
            
    async def high_output_test(self):
        """Test high-output process (back-pressure handling)"""
        print("\n=== Testing High Output Process ===")
        
        result = await self.single_session_test(
            "high-output",
            "python -c 'for i in range(10000): print(f\"Line {i}: \" + \"x\" * 100)'"
        )
        
        print(f"✓ Processed {result['output_lines']} output lines")
        print(f"✓ Duration: {result['duration']:.2f}s")
        print(f"✓ Rate: {result['output_lines'] / result['duration']:.0f} lines/second")
        
        return result
        
    async def run_all_tests(self):
        """Run all stress tests"""
        marker = f"WEBSOCKET_STRESS_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"{marker}: Starting WebSocket MCP Stress Tests")
        
        # Test 1: Single session
        print("\n=== Test 1: Single Session ===")
        result = await self.single_session_test("test-1", "echo 'Hello from stress test'")
        print(f"✓ Success: {result['success']}, Duration: {result['duration']:.2f}s")
        
        # Test 2: Multiple concurrent sessions
        for num in [5, 10, 20]:
            await self.concurrent_sessions_test(num)
            await asyncio.sleep(1)  # Brief pause between tests
            
        # Test 3: Process control
        await self.process_control_test()
        
        # Test 4: High output
        await self.high_output_test()
        
        print(f"\n{marker}: All tests completed")


if __name__ == "__main__":
    # Check if service is running
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if sock.connect_ex(('localhost', 8003)) != 0:
        print("❌ cc_executor service not running on port 8003")
        print("Start it with: docker compose up")
        exit(1)
    sock.close()
    
    # Run stress tests
    tester = WebSocketStressTest()
    asyncio.run(tester.run_all_tests())
```

## Recovery Tests

1. **Service Down**: Handle connection refused gracefully
2. **Session Limit**: Test behavior when max sessions reached
3. **Command Validation**: Test rejected commands
4. **Memory Limits**: Verify no memory leaks under load

## Success Criteria

- [ ] All single session tests pass
- [ ] 90%+ success rate for concurrent sessions
- [ ] Process control works reliably
- [ ] High output doesn't cause memory issues
- [ ] No crashes or hangs
- [ ] Response times remain reasonable (<5s for simple commands)