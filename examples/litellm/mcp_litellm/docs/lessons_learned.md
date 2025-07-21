# Lessons Learned

## Errors & Fixes (Pre-Phase 5)

*   **AttributeError (`item.mode`) in engine.py:** The code in `engine.py` (around line 123 in the `process_batch` function) incorrectly accessed `item.mode` to check the execution method. The correct attribute in the `QuestionItem` model (defined in `models.py`) is `item.method`. Corrected the code to use `item.method == "concurrent"`.
*   **AttributeError (`item.messages`) in engine.py:** The code in `engine.py` (around line 172 in the `process_batch` function) tried to access `item.messages`, which does not exist on the `QuestionItem` model. The model only has `item.question`. The code should always construct the `messages` list for LiteLLM using `item.question`. Corrected line 172 to remove the check for `item.messages`.
*   **AttributeError (`item.retry_*`) in engine.py:** The code in `engine.py` (around lines 199-203 in the `process_batch` function) incorrectly tried to access retry parameters (`retry_initial_delay`, `retry_max_delay`, `retry_backoff_factor`, `retry_max_retries`, `retry_codes`) from the `item` (`QuestionItem`) object. These attributes are not defined in the `QuestionItem` model. Removed these arguments from the `retry_llm_call` invocation, allowing the retry function to use its defaults or handle them internally.
*   **Incorrect Argument Passing in `retry_llm_call.py`:** The `retry_llm_call` function was receiving a `QuestionItem` object but treating it as a dictionary (`Dict`). It passed the `QuestionItem` directly to the underlying `litellm_call` (which expects a `Dict`) and tried to access non-existent nested keys (`llm_config["llm_config"]["messages"]`). Corrected `retry_llm_call` to accept `QuestionItem`, construct the necessary `config: Dict` (including the `messages` list from `QuestionItem.question`), and modify the local `messages` list for retry feedback.
*   **Incorrect Dictionary Structure for `litellm_call`:** The `litellm_call` function expects a nested dictionary structure like `{"llm_config": {"model": ..., "messages": ...}}`. The previous fix in `retry_llm_call` constructed a flat dictionary. Corrected `retry_llm_call` to build the `call_config` dictionary with the required nested `"llm_config"` key. The retry logic was also updated to modify `call_config["llm_config"]["messages"]`.
*   **Incorrect Access in `mock_litellm_call` (engine.py):** The mock function `mock_litellm_call` was defined to accept `QuestionItem` and accessed attributes like `llm_config.messages`. However, after fixing `retry_llm_call`, it now receives the nested dictionary `call_config = {"llm_config": {...}}`. Updated `mock_litellm_call` to expect a `Dict` and access parameters via the nested structure (e.g., `llm_config["llm_config"]["messages"]`).
*   **Mock Function Mismatch (engine.py):** The example in `engine.py` uses `mock_retry_llm_call` which passes the `QuestionItem` directly to `mock_litellm_call`. However, `mock_litellm_call` was incorrectly modified to expect a nested dictionary (like the real `litellm_call`). Reverted `mock_litellm_call` to expect `QuestionItem` and access attributes directly (e.g., `llm_config.question`, `llm_config.model`) for the example run.
*   **Debugging Task Exceptions:** When tasks run via `asyncio.gather` fail, the exception object is returned in the results list. The initial error logging only showed the string representation (`str(exception)`), which was misleading. Modified the error logging in `engine.py` (line 234) to include `type(exception)` and `repr(exception)` to get a clearer picture of the actual error occurring within the task.

## Phase 5 - Refactoring to DAG Architecture

**Phase 5 - Architect/Boomerang:**

*   **Explicit DAG Definition:** Clearly defining DAG nodes (functions) and their dependencies upfront using tools like `networkx` was crucial for visualizing and validating the execution flow before implementation.
*   **Modularity Pays Off:** Designing with independent, reusable functions (nodes) simplified the refactoring, improved code structure, and made testing individual components easier.
*   **Dependency Mapping:** Thoroughly mapping data dependencies between nodes was essential to prevent errors and ensure the correct execution order. Pydantic models helped enforce consistent input/output schemas between nodes.
*   **Error Propagation Strategy:** Defining how errors in one node impact downstream execution (e.g., halt vs. continue with partial results) required careful consideration during the design phase to ensure robustness.

**Phase 5 - Code:**

*   **Incremental Refactoring:** Breaking down the refactoring of procedural code into a DAG structure into smaller, testable steps was vital for managing complexity.
*   **DAG Execution Testing:** Specific tests were needed to verify correct node execution order, dependency handling, and data flow within the DAG. Mocking node dependencies was crucial for unit testing.
*   **Async Complexity:** Integrating the DAG with `asyncio` for potential concurrency added complexity, requiring careful management of `async`/`await` and robust error handling for concurrent tasks.
*   **Debugging Data Flow:** Implementing detailed logging at the entry/exit points of each DAG node was essential for tracing data transformations and debugging issues within the execution flow.
*   **Integrating `networkx`:** While `networkx` defined the structure, custom logic was needed to traverse the graph, execute the corresponding functions, and manage the passing of data between nodes according to the defined dependencies.

**Phase 5 - Planner:**

*   **Plan Adaptability:** Verification steps are critical. The failure of the initial sequential logic (Task 5.4.1) highlighted a design flaw, necessitating a pivot. Updating the plan document (`task.md`) immediately to reflect major changes (like adopting a new architecture) is essential for maintaining clarity and direction.
*   **Precise Delegation:** Delegating complex refactoring tasks requires clear instructions outlining the expected inputs, outputs, and core changes (e.g., specifying model updates alongside engine refactoring).
*   **Environment Context for Execution:** Tool execution context matters. Git commands failed initially due to being run in the wrong directory and later due to unignored embedded repositories, requiring `.gitignore` updates. Always verify the execution context (CWD, environment state) before running commands.
*   **Task Tracking:** Maintaining the checklist (`[X]`, `[ ]`, `[F]`) in `task.md` accurately is crucial for tracking progress and understanding the project state, especially when tasks are added, modified, or marked as failed/obsolete.

## Phase 7 - Agent-Queryable Lessons Learned

**Phase 7 - Code/Boomerang:**

*   **Environment Sensitivity:** Local embedding models (like HuggingFace Transformers) are highly sensitive to Python environment inconsistencies, particularly versions of `torch`, `numpy`, and `transformers`. Mismatches can lead to obscure errors (`init_empty_weights`, NumPy compatibility warnings). Pinning dependencies (`numpy<2.0`) and potentially rebuilding the environment (`uv sync`) are crucial debugging steps.
*   **API vs Local Embeddings:** For non-GPU environments (like macOS without CUDA), relying on local transformer models for embeddings is inefficient and prone to failure. Switching to a cloud API (like OpenAI) is a more robust and performant solution, though it requires managing API keys and potential costs.
*   **Vector Dimension Consistency:** When switching embedding models (e.g., local BGE to OpenAI), ensure the vector dimensions are consistent across the query and the stored data. Re-embedding existing data is necessary if dimensions change (e.g., 1024 to 1536).
*   **ArangoDB Indexing:** Creating vector indexes (inverted indexes) using the `python-arango` driver can be version-sensitive. Methods like `add_vector_index`, `add_inverted_index`, `ensure_index`, and `add_index` have varying availability and syntax across driver/server versions. Specifying the `analyzer` (e.g., `identity`) is critical for indexing array fields like embeddings. If driver methods fail, using raw AQL `ensureIndex` might work, but the most reliable driver method is typically `add_index` with a full options dictionary. Failure to create the index requires removing index hints from AQL queries to allow fallback to collection scans.
*   **AQL Syntax:** AQL has specific syntax (e.g., `POW()` for exponentiation, no `#` comments within queries) that must be strictly followed. Built-in functions like `COSINE_SIMILARITY` are preferred over manual calculations when available and appropriate indexes exist.
*   **Database Configuration:** Test scripts must be configured with the correct database name and credentials. Using placeholder or default values (like `_system` db) will lead to connection or data access errors.
*   **Proactive Documentation Check:** Relying solely on potentially outdated model knowledge for library/API usage (like `python-arango` index creation) can lead to significant delays and errors. Proactively consulting official documentation or using research tools (like Perplexity) is essential for complex or version-sensitive features.

## Security Implementation and Known Limitations (Task 9.2)

**Parser.py Security Model:**
- The `parser.py` module now includes robust input validation and sanitization routines to ensure that only expected data types are processed and to protect against code injection attacks.
- Strict type-checking and data format verifications are applied, mitigating risks from malformed inputs and unauthorized function calls.
- Comprehensive Unicode XSS protection including:
  - Turkish dotless i variants (ı, İ)
  - FE64/FE65 Unicode points
- Explicit rejection of complex numbers
- Enhanced custom object sanitization

**Known Limitations:**
- Validation for very large inputs could incur performance overhead under peak conditions.
- Recursive object sanitization may not capture all deeply nested or dynamically generated malicious content.
- Some Unicode normalization edge cases may still bypass detection.

**Future Work:**
- Create specific tickets to address performance optimizations.
- Develop additional test scenarios for Unicode normalization edge cases.
- Monitor for new XSS attack vectors requiring pattern updates.

**Version:** 1.1 (2025-04-07)