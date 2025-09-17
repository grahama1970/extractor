import asyncio
import sys
import time

import pytest

from extractor.pipeline.utils.codex_call import run_codex_exec


def test_overall_timeout_terminates_quickly(tmp_path):
    # Arrange: long sleep command (~5s)
    cmd = "-c"
    code = "import time; time.sleep(5)"

    t0 = time.monotonic()
    res = asyncio.run(
        run_codex_exec(
            script_or_path=cmd,
            codex_bin=sys.executable,
            extra_args=[code],
            prepend_exec=False,  # raw mode: run python -c ...
            overall_timeout_s=1.0,  # 1s overall timeout
            idle_timeout_s=None,
            stdout_capture_limit=0,
            stderr_capture_limit=0,
        )
    )
    dt = time.monotonic() - t0

    # Assert: timed out and finished well under the original 5s
    assert res.timed_out is True
    assert dt < 3.0


def test_idle_timeout_triggers_without_overall_timeout(tmp_path):
    # Arrange: prints once, then sleeps 5s to trigger idle
    cmd = "-c"
    code = (
        "import sys, time; sys.stdout.write('start\\n'); sys.stdout.flush(); time.sleep(5)"
    )

    # Capture chunks to a list
    out_chunks = []

    def on_out(b: bytes):
        out_chunks.append(b)

    res = asyncio.run(
        run_codex_exec(
            script_or_path=cmd,
            codex_bin=sys.executable,
            extra_args=[code],
            prepend_exec=False,
            overall_timeout_s=10.0,
            idle_timeout_s=1.0,  # idle for 1s should terminate
            on_stdout_chunk=on_out,
            stdout_capture_limit=0,
            stderr_capture_limit=0,
        )
    )

    # Assert: idle timeout engaged, and we saw initial output
    assert res.idle_timed_out is True
    assert any(b"start" in c for c in out_chunks)

