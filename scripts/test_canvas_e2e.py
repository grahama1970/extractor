#!/usr/bin/env python3
"""End-to-end mock persona conversation test for the 5ft voice canvas.

Simulates a persona (Margaret) asking a question via text (mocked STT),
receiving a D3 visualization, then manipulating the graph via follow-up
voice commands. Validates the full pipeline:

  Voice (mocked) → STT (skipped) → Intent Classification → /memory recall
  → /analytics profiling → Chart Type Selection → /figure-lab rendering
  → D3 Manipulation → Session Archival

Usage:
    python scripts/test_canvas_e2e.py                    # Full e2e test
    python scripts/test_canvas_e2e.py --server localhost:8003  # Custom server
    python scripts/test_canvas_e2e.py --dry-run            # Parse only, no HTTP
    python scripts/test_canvas_e2e.py --verbose            # Show full SSE events

Requires the agent endpoint server running:
    cd prototypes/tabbed/api && uvicorn review_server:app --port 8003
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Optional

try:
    import httpx
except ImportError:
    print("pip install httpx")
    sys.exit(1)


# --- Test Conversation ---
# Margaret asks about compliance data, gets a chart, then manipulates it.

CONVERSATIONS = [
    {
        "name": "Margaret: Compliance Score Heatmap",
        "persona": "margaret",
        "turns": [
            # Turn 1: Initial query → should produce a visualization
            {
                "query": "Show me a heatmap of compliance scores across all document domains",
                "expect_type": "html",
                "expect_intent": "VISUALIZE",
                "description": "Initial chart request",
            },
            # Turn 2: Manipulation → zoom into a specific area
            {
                "query": "Zoom in on the defense specifications cluster",
                "expect_manipulation": True,
                "expect_actions": ["zoom_in"],
                "description": "Zoom manipulation",
            },
            # Turn 3: Manipulation → highlight specific nodes
            {
                "query": "Highlight the documents with scores below 0.7",
                "expect_manipulation": True,
                "expect_actions": ["highlight"],
                "description": "Highlight manipulation",
            },
            # Turn 4: Manipulation → reset view
            {
                "query": "Reset the view",
                "expect_manipulation": True,
                "expect_actions": ["reset"],
                "description": "Reset manipulation",
            },
        ],
    },
    {
        "name": "Jennifer: Table Fidelity Trend",
        "persona": "jennifer",
        "turns": [
            # Turn 1: Ask for a trend line
            {
                "query": "Show me the table fidelity trend over the last 100 extractions",
                "expect_type": "html",
                "expect_intent": "VISUALIZE",
                "description": "Trend chart request",
            },
            # Turn 2: Focus on a specific point
            {
                "query": "Focus on the dip around extraction 45",
                "expect_manipulation": True,
                "expect_actions": ["focus"],
                "description": "Focus manipulation",
            },
            # Turn 3: Compare with related data
            {
                "query": "Now compare table fidelity with content coverage as a radar chart",
                "expect_type": "html",
                "expect_intent": "COMPARE",
                "description": "New chart from follow-up query",
            },
        ],
    },
    {
        "name": "Embry: Network Graph Exploration",
        "persona": "embry",
        "turns": [
            # Turn 1: Ask for a network graph
            {
                "query": "Show me the document cross-reference network for MIL-STD documents",
                "expect_type": "html",
                "expect_intent": "VISUALIZE",
                "description": "Network graph request",
            },
            # Turn 2: Highlight related nodes
            {
                "query": "Highlight MIL-STD-1553 and show all related nodes",
                "expect_manipulation": True,
                "expect_actions": ["highlight_related", "highlight"],
                "description": "Highlight related nodes",
            },
            # Turn 3: Expand a node
            {
                "query": "Expand the MIL-STD-1553 node to show its sub-requirements",
                "expect_manipulation": True,
                "expect_actions": ["expand"],
                "description": "Expand node",
            },
            # Turn 4: Filter
            {
                "query": "Filter to show only nodes with more than 3 connections",
                "expect_manipulation": True,
                "expect_actions": ["filter"],
                "description": "Filter by connection count",
            },
        ],
    },
]


class TestResult:
    """Track and report test results with pass/fail counts and error messages."""
    def __init__(self, name: str):
        """Initialize an object with a name and counters for passed/failed."""
        self.name = name
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []

    def ok(self, msg: str):
        """Log a passed test message and increment the counter."""
        self.passed += 1
        print(f"  ✓ {msg}")

    def fail(self, msg: str):
        """Record failure message and increment error count."""
        self.failed += 1
        self.errors.append(msg)
        print(f"  ✗ {msg}")

    @property
    def total(self):
        """Return the sum of passed and failed counts."""
        return self.passed + self.failed


def test_ask_stream(
    server: str,
    query: str,
    persona: str,
    verbose: bool = False,
) -> dict:
    """Send a query to /api/agent/ask-stream and parse SSE response."""
    url = f"http://{server}/api/agent/ask-stream"
    events = []

    with httpx.Client(timeout=60.0) as client:
        with client.stream(
            "POST", url,
            json={"query": query, "persona": persona},
        ) as resp:
            resp.raise_for_status()
            buffer = ""
            current_event = ""

            for chunk in resp.iter_text():
                buffer += chunk
                lines = buffer.split("\n")
                buffer = lines.pop()

                for line in lines:
                    if line.startswith("event: "):
                        current_event = line[7:].strip()
                    elif line.startswith("data: ") and current_event:
                        try:
                            data = json.loads(line[6:])
                            events.append({"event": current_event, "data": data})
                            if verbose:
                                print(f"    SSE: {current_event} → {json.dumps(data)[:200]}")
                        except json.JSONDecodeError:
                            pass
                        current_event = ""

    # Extract results
    result = {
        "events": events,
        "statuses": [e["data"] for e in events if e["event"] == "status"],
        "answer": next((e["data"] for e in events if e["event"] == "answer"), None),
        "manipulation": next((e["data"] for e in events if e["event"] == "manipulate"), None),
        "error": next((e["data"] for e in events if e["event"] == "error"), None),
    }
    return result


def test_classify_only(query: str) -> dict:
    """Dry-run: test intent classification + manipulation detection without HTTP."""
    # Import the classifier functions directly
    sys.path.insert(0, "prototypes/tabbed/api")
    try:
        from agent_endpoint import (
            classify_intent,
            _is_manipulation_command,
            _parse_manipulation_commands,
            _should_visualize,
        )
    except ImportError as e:
        return {"error": str(e)}

    is_manip = _is_manipulation_command(query)
    if is_manip:
        commands = _parse_manipulation_commands(query)
        return {
            "is_manipulation": True,
            "commands": commands,
            "actions": [c["action"] for c in commands],
        }
    else:
        classification = classify_intent(query)
        stage1 = _should_visualize(query)
        return {
            "is_manipulation": False,
            "intent": classification["intent"],
            "confidence": classification["confidence"],
            "source": classification["source"],
            "should_visualize": stage1["decision"],
        }


def run_conversation(
    conv: dict,
    server: str,
    verbose: bool = False,
    dry_run: bool = False,
) -> TestResult:
    """Run a full conversation and validate each turn."""
    result = TestResult(conv["name"])
    persona = conv["persona"]
    print(f"\n{'='*60}")
    print(f"Conversation: {conv['name']}")
    print(f"Persona: {persona}")
    print(f"{'='*60}")

    for i, turn in enumerate(conv["turns"]):
        print(f"\n  Turn {i+1}: {turn['description']}")
        print(f"  Query: \"{turn['query']}\"")

        if dry_run:
            # Classification-only mode
            res = test_classify_only(turn["query"])
            if "error" in res:
                result.fail(f"Import error: {res['error']}")
                continue

            if turn.get("expect_manipulation"):
                if res.get("is_manipulation"):
                    result.ok(f"Detected as manipulation: {res.get('actions', [])}")
                    # Check expected actions
                    for expected in turn.get("expect_actions", []):
                        if any(expected in a for a in res.get("actions", [])):
                            result.ok(f"Action '{expected}' found")
                        else:
                            result.fail(f"Expected action '{expected}' not found in {res.get('actions', [])}")
                else:
                    result.fail(f"Expected manipulation, got intent: {res.get('intent')}")
            else:
                if not res.get("is_manipulation"):
                    result.ok(f"Classified as {res.get('intent')} ({res.get('confidence', 0):.0%})")
                    if turn.get("expect_intent"):
                        if res.get("intent") == turn["expect_intent"]:
                            result.ok(f"Intent matches expected: {turn['expect_intent']}")
                        else:
                            result.fail(f"Expected intent {turn['expect_intent']}, got {res.get('intent')}")
                else:
                    result.fail(f"Expected query, got manipulation: {res.get('actions')}")
        else:
            # Full HTTP e2e test
            try:
                start = time.time()
                res = test_ask_stream(server, turn["query"], persona, verbose)
                elapsed = time.time() - start

                if res.get("error"):
                    result.fail(f"Server error: {res['error'].get('message', 'unknown')}")
                    continue

                result.ok(f"Response in {elapsed:.1f}s ({len(res['events'])} SSE events)")

                if turn.get("expect_manipulation"):
                    if res.get("manipulation"):
                        commands = res["manipulation"].get("commands", [])
                        actions = [c["action"] for c in commands]
                        result.ok(f"Manipulation: {actions}")

                        for expected in turn.get("expect_actions", []):
                            if any(expected in a for a in actions):
                                result.ok(f"Action '{expected}' found")
                            else:
                                result.fail(f"Expected action '{expected}' not in {actions}")
                    else:
                        result.fail("Expected manipulation event, got answer/none")

                else:
                    if res.get("answer"):
                        answer = res["answer"]
                        atype = answer.get("type", "unknown")
                        title = answer.get("title", "untitled")
                        source = answer.get("source", "")
                        viz_family = answer.get("vizFamily", "")
                        result.ok(f"Answer: type={atype}, title='{title}'")

                        if turn.get("expect_type"):
                            if atype == turn["expect_type"]:
                                result.ok(f"Type matches: {turn['expect_type']}")
                            else:
                                result.fail(f"Expected type {turn['expect_type']}, got {atype}")

                        if atype == "html":
                            content_len = len(answer.get("content", ""))
                            has_d3 = "d3" in answer.get("content", "").lower()
                            has_runtime = "d3-manipulate" in answer.get("content", "")
                            result.ok(f"HTML: {content_len} bytes, D3={has_d3}, runtime={has_runtime}")

                            if not has_runtime:
                                result.fail("Manipulation runtime NOT injected into HTML")

                        # Check classification metadata
                        classification = answer.get("_classification", {})
                        if classification:
                            intent = classification.get("intent", "unknown")
                            conf = classification.get("confidence", 0)
                            src = classification.get("source", "unknown")
                            result.ok(f"Classification: {intent} ({conf:.0%}) via {src}")

                            if turn.get("expect_intent") and intent != turn["expect_intent"]:
                                result.fail(f"Expected intent {turn['expect_intent']}, got {intent}")
                    else:
                        result.fail("No answer event received")

                # Check statuses were emitted
                status_names = [s.get("status") for s in res.get("statuses", [])]
                if status_names:
                    result.ok(f"Statuses: {' → '.join(status_names)}")
                else:
                    result.fail("No status events emitted")

            except httpx.ConnectError:
                result.fail(f"Cannot connect to {server} — is the server running?")
                break
            except Exception as e:
                result.fail(f"Exception: {e}")

    return result


def test_session_lifecycle(server: str) -> TestResult:
    """Test session tracking: query → manipulate → flush → verify."""
    result = TestResult("Session Lifecycle")
    print(f"\n{'='*60}")
    print("Test: Session Lifecycle (query → manipulate → flush)")
    print(f"{'='*60}")

    try:
        client = httpx.Client(base_url=f"http://{server}", timeout=30.0)

        # Step 1: Check initial session status
        resp = client.get("/api/agent/session/status")
        if resp.status_code == 200:
            result.ok("Session status endpoint works")
        else:
            result.fail(f"Session status failed: {resp.status_code}")

        # Step 2: Run a query to create a session
        print("\n  Sending initial query...")
        with client.stream(
            "POST", "/api/agent/ask-stream",
            json={"query": "Show me extraction quality scores as a bar chart", "persona": "test_persona"},
        ) as resp:
            resp.raise_for_status()
            # Consume the stream
            for _ in resp.iter_text():
                pass
        result.ok("Query sent, session should be active")

        # Step 3: Check session exists
        resp = client.get("/api/agent/session/status")
        sessions = resp.json().get("active_sessions", {})
        if "test_persona" in sessions:
            s = sessions["test_persona"]
            result.ok(f"Session active: {s['session_id']} ({s['turns']} turns)")
        else:
            result.fail("No session found for test_persona after query")

        # Step 4: Send manipulation
        print("  Sending manipulation...")
        with client.stream(
            "POST", "/api/agent/ask-stream",
            json={"query": "Zoom in on the highest bar", "persona": "test_persona"},
        ) as resp:
            resp.raise_for_status()
            for _ in resp.iter_text():
                pass
        result.ok("Manipulation sent")

        # Step 5: Check manipulation count
        resp = client.get("/api/agent/session/status")
        sessions = resp.json().get("active_sessions", {})
        if "test_persona" in sessions:
            manips = sessions["test_persona"].get("manipulations", 0)
            if manips > 0:
                result.ok(f"Manipulation tracked: {manips} manipulations")
            else:
                result.fail("Manipulation count is 0")
        else:
            result.fail("Session disappeared after manipulation")

        # Step 6: Flush session
        print("  Flushing session...")
        resp = client.post(
            "/api/agent/session/flush",
            json={"query": "", "persona": "test_persona"},
        )
        flush = resp.json()
        if flush.get("flushed"):
            result.ok(f"Session flushed: {flush.get('session_id')} ({flush.get('turns')} turns)")
        else:
            result.fail(f"Flush failed: {flush}")

        # Step 7: Verify session is gone
        resp = client.get("/api/agent/session/status")
        sessions = resp.json().get("active_sessions", {})
        if "test_persona" not in sessions:
            result.ok("Session cleared after flush")
        else:
            result.fail("Session still active after flush")

        # Step 8: Check session file on 12TB drive
        import glob
        session_files = glob.glob("/mnt/storage12tb/artifacts/canvas_sessions/*test_persona*.json")
        if session_files:
            result.ok(f"Session persisted to 12TB: {session_files[-1]}")
        else:
            result.fail("No session file found on 12TB drive")

        client.close()
    except httpx.ConnectError:
        result.fail(f"Cannot connect to {server}")
    except Exception as e:
        result.fail(f"Exception: {e}")

    return result


def main():
    """Run an E2E canvas conversation test."""
    parser = argparse.ArgumentParser(description="E2E canvas conversation test")
    parser.add_argument("--server", default="127.0.0.1:8003", help="Agent endpoint server")
    parser.add_argument("--dry-run", action="store_true", help="Classification only, no HTTP")
    parser.add_argument("--verbose", action="store_true", help="Show full SSE events")
    parser.add_argument("--conversation", type=int, help="Run specific conversation (0-indexed)")
    parser.add_argument("--session-test", action="store_true", help="Run session lifecycle test only")
    args = parser.parse_args()

    results: list[TestResult] = []

    if args.session_test:
        results.append(test_session_lifecycle(args.server))
    elif args.conversation is not None:
        if 0 <= args.conversation < len(CONVERSATIONS):
            results.append(run_conversation(
                CONVERSATIONS[args.conversation], args.server, args.verbose, args.dry_run,
            ))
        else:
            print(f"Invalid conversation index. Available: 0-{len(CONVERSATIONS)-1}")
            sys.exit(1)
    else:
        # Run all conversations
        for conv in CONVERSATIONS:
            results.append(run_conversation(conv, args.server, args.verbose, args.dry_run))
        # Also run session lifecycle test
        if not args.dry_run:
            results.append(test_session_lifecycle(args.server))

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    total_pass = 0
    total_fail = 0
    for r in results:
        status = "PASS" if r.failed == 0 else "FAIL"
        print(f"  [{status}] {r.name}: {r.passed}/{r.total} checks passed")
        total_pass += r.passed
        total_fail += r.failed
        for err in r.errors:
            print(f"        ✗ {err}")

    print(f"\nTotal: {total_pass}/{total_pass + total_fail} checks passed")
    if total_fail > 0:
        print(f"\n{total_fail} FAILURES")
        sys.exit(1)
    else:
        print("\nALL TESTS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
