# 01_SPEC: Hardened Tasks Loop Architecture

**Version**: 1.0.0
**Status**: APPROVED

## 1. Core Philosophy: "The Enterprise Backbone"

The pipeline uses a **Contract-Driven** architecture (`tasks_loop`) to ensure deterministic execution and validation. We explicitly verify capabilities _before_ integrating them.

### 1.1 Non-Negotiables

1.  **Fixtures are Prerequisites**: No code is written without a `SPEC.md` and a corresponding **High-Fidelity Fixture** (Mimic).
    - _Applies to_: PDFs, Datasets, JSON, HTML.
    - _Standard_: "Messy" real-world mimics, not "clean" synthetic toys.
2.  **Define Done**: `SPEC.md` defines the exact success criteria (e.g., "118 blocks detected") before implementation.
3.  **Headless Visibility**: The system must emit machine-readable status (`status.json`) and enforce tee'd logs so the agent is never blind.

---

## 2. Architecture Enhancements

We are hardening the existing `tasks_loop` with isolation and resilience patterns.

### 2.1 Run Isolation (Pi-Style)

**Problem**: `data/results/pipeline` is a global mutable state, causing bleeding between runs.
**Spec**:

- Every execution must generate a unique `run_id` (UUID or Timestamp).
- All step outputs go to `data/results/{run_id}/{step_output}/`.
- `latest` symlink points to the most recent `run_id` for easy debugging.

```python
# run_pipeline.py pattern
run_id = f"run_{timestamp}_{uuid}"
config = PipelineConfig(output_root=f"data/results/{run_id}")
```

### 2.2 Process-Level Retries (Ralph-Style)

**Problem**: PDF parsing libraries (C-bindings) and OOM killers cause Segfaults/SIGKILLs that Python `tenacity` decorators cannot catch within the process.
**Spec**:

- Steps are executed as **Subprocesses** via `run_pipeline.py`.
- The Runner implements a **Retry Decorator** around the `subprocess.run` call.
- _Policy_: Retry 3 times on Exit Code != 0 (excluding explicit configuration errors).

```python
@retry_subprocess(attempts=3, delay=1.0)
def execute_step(cmd):
    return subprocess.run(cmd, check=True)
```

### 2.3 Headless Observability

**Problem**: The headless agent blindly executes commands and greps logs.
**Spec**:

- **Status Artifact**: `data/results/{run_id}/status.json` updated atomically after each step.
- **Failure Report**: `data/results/{run_id}/gate_failure.json` generated on verification failure.
- **Tee'd Logs**: Wrapper forces stdout/stderr to both console (for agent) and `run.log` (for history).

---

## 3. Directory Structure

```text
data/
└── results/
    ├── run_20260113_1042/  <-- ISOLATED CONTEXT
    │   ├── status.json
    │   ├── run.log
    │   ├── 02_marker_blocks/
    │   ├── 07_tables/
    │   └── ...
    └── latest -> run_20260113_1042
```

## 4. Implementation Plan

1.  **Refactor `run_pipeline.py`**: Add `RunContext` class and `--run-id` arg.
2.  **Update Step Contracts**: Ensure all steps accept `--output-dir` arguments (no hardcoded paths).
3.  **Implement `retry_utils.py`**: The subprocess retry decorator.
4.  **Add `status_reporter.py`**: Metadata writer.
