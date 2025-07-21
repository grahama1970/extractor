"""
Module: engine.py
Description: Model Context Protocol (MCP) integration

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

# -*- coding: utf-8 -*-
"""
MCP LiteLLM Service: Asynchronous Execution Engine

Description:
------------
This module implements the core asynchronous engine for processing batches
of LLM requests using LiteLLM. It handles concurrent and sequential execution,
dependency management (result substitution), retries with backoff, and
pluggable validation strategies.

Core Libraries/Concepts:
------------------------
- asyncio: For managing asynchronous tasks and concurrency.
- typing: For precise type hinting.
- loguru: For logging.
- LiteLLM: The underlying library for interacting with various LLM APIs.

Key Components:
---------------
- `process_batch`: The main entry point function that orchestrates the
  processing of a `BatchRequest`.
- Dependency Handling: Sequential tasks can depend on the results of
  previous tasks using placeholder syntax (e.g., `{Q1_result}`).
- Concurrency: Concurrent tasks are executed in parallel using `asyncio.gather`.
- Error Handling: Captures exceptions during task execution and substitution.
- Retries: Leverages `retry_llm_call` for robust LLM interactions.
- Validation: Supports optional validation strategies (e.g., Pydantic).

Sample I/O (Conceptual):
------------------------
Input (`BatchRequest`):
{
  "questions": [
    {"index": 0, "question": "What is the capital of France?", "mode": "concurrent", "model": "gpt-3.5-turbo"},
    {"index": 1, "question": "Summarize this: {Q0_result}", "mode": "sequential", "model": "gpt-3.5-turbo"},
    {"index": 2, "question": "Is Paris sunny?", "mode": "concurrent", "model": "gpt-3.5-turbo"}
  ]
}

Output (`BatchResponse`):
{
  "results": [
    {"index": 0, "status": "success", "result": "Paris", "retry_count": 0},
    {"index": 1, "status": "success", "result": "Paris is the capital.", "retry_count": 1},
    {"index": 2, "status": "error", "result": "API connection error", "retry_count": 3}
  ]
}
"""

import asyncio
import traceback
from typing import List, Dict, Any, Optional, Callable, Tuple, Set

from loguru import logger

# Assuming models are defined in .models relative to this file's location in the package
from .models import (
    BatchRequest,
    BatchResponse,
    TaskItem,
    ResultItem,
    # Import specific Pydantic models if needed for validation, or handle dynamically
)
from .litellm_call import litellm_call # The core function to call LiteLLM
from .retry_llm_call import retry_llm_call # The retry wrapper
from .parser import substitute_results # For handling result substitution


# --- Placeholder for Pydantic Validation ---
# This section might involve dynamically importing models or defining placeholder functions
# For now, a simple placeholder.
def get_pydantic_validator(model_name: str) -> Optional[Callable[[Any], Any]]:
    """
    Retrieves or creates a Pydantic validation function based on model name.
    Placeholder implementation.
    """
    logger.warning(f"Pydantic validation requested for {model_name}, but not fully implemented yet.")
    # In a real implementation, you might dynamically import a model from .models
    # or have a registry.
    # Example:
    # try:
    #     from . import models
    #     model_cls = getattr(models, model_name)
    #     def validator(data):
    #         return model_cls.model_validate(data)
    #     return validator
    # except (ImportError, AttributeError) as e:
    #     logger.error(f"Could not find or import Pydantic model '{model_name}': {e}")
    #     return None
    return None # Return None if validation cannot be performed

# --- Core Engine ---

async def process_batch(request: BatchRequest) -> BatchResponse:
    """
    Processes a batch of LLM tasks asynchronously using a DAG-based execution engine.

    Args:
        request: The BatchRequest containing tasks with dependencies.

    Returns:
        A BatchResponse containing the results for each task.

    Raises:
        ValueError: If dependency chain exceeds maximum allowed depth (20)
    """
    from .parser import substitute_placeholders

    MAX_DEPTH = 20  # Maximum allowed dependency chain depth

    # Validate dependency chain depth before processing
    def calculate_max_depth(task_id: str, visited: Set[str] = None, current_depth: int = 0) -> int:
        """Calculate maximum dependency depth for a task."""
        if visited is None:
            visited = set()
        if task_id in visited:
            return current_depth
        visited.add(task_id)
        
        max_depth = current_depth
        for dep in dependencies.get(task_id, []):
            depth = calculate_max_depth(dep, visited.copy(), current_depth + 1)
            if depth > max_depth:
                max_depth = depth
        return max_depth

    task_map: Dict[str, TaskItem] = {task.task_id: task for task in request.tasks}
    dependencies: Dict[str, Set[str]] = {task.task_id: set(task.dependencies) for task in request.tasks}

    # Check all tasks for excessive dependency depth
    for task_id in task_map:
        depth = calculate_max_depth(task_id)
        if depth > MAX_DEPTH:
            raise ValueError(
                f"Dependency chain for task {task_id} exceeds maximum allowed depth of {MAX_DEPTH}. "
                f"Found depth: {depth}. Simplify your task dependencies."
            )
    dependents: Dict[str, Set[str]] = {task_id: set() for task_id in task_map}
    in_degree: Dict[str, int] = {}

    # Add sequential dependencies
    for i, task in enumerate(request.tasks):
        if task.method == "sequential" and not task.dependencies and i > 0:
            prev_task = request.tasks[i-1]
            if prev_task.method != "concurrent":
                dependencies[task.task_id].add(prev_task.task_id)

    # Build reverse dependency map and in-degree count
    for task_id, deps in dependencies.items():
        in_degree[task_id] = len(deps)
        for dep in deps:
            dependents.setdefault(dep, set()).add(task_id)

    completed_results: Dict[str, ResultItem] = {}
    ready_queue: asyncio.Queue = asyncio.Queue()

    # Initialize ready queue with tasks having zero dependencies
    for task_id, deg in in_degree.items():
        if deg == 0:
            ready_queue.put_nowait(task_id)

    semaphore = asyncio.Semaphore(5)  # Default max concurrency, can be parameterized

    async def run_task(task_id: str):
        task = task_map[task_id]
        await semaphore.acquire()
        try:
            # Substitute placeholders in question
            substituted_question = substitute_placeholders(task.question, completed_results)
            task.question = substituted_question

            # Prepare validation strategies
            validation_strategies: List[Callable[[Any], Any]] = []
            if task.validation_strategy == "pydantic" and task.response_model:
                validator = get_pydantic_validator(task.response_model)
                if validator:
                    validation_strategies.append(validator)
                else:
                    raise ValueError(f"Pydantic validator for model '{task.response_model}' could not be created.")

            messages = [{"role": "user", "content": substituted_question}]

            logger.debug(f"Running task {task_id} with substituted question: {substituted_question}")

            response_obj, retry_count = await retry_llm_call(
                llm_call=litellm_call,
                model=task.model,
                messages=messages,
                temperature=task.temperature,
                max_tokens=task.max_tokens,
                api_base=task.api_base,
                response_model=task.response_model,
                validation_strategies=validation_strategies,
            )

            # Extract content
            content_to_store = None
            if hasattr(response_obj, 'choices') and response_obj.choices:
                if hasattr(response_obj.choices[0], 'message') and hasattr(response_obj.choices[0].message, 'content'):
                    content_to_store = response_obj.choices[0].message.content

            if content_to_store is not None:
                result_item = ResultItem(
                    task_id=task_id,
                    status="success",
                    result=content_to_store,
                    retry_count=retry_count
                )
            else:
                result_item = ResultItem(
                    task_id=task_id,
                    status="error",
                    result=f"Could not extract content from response object: {response_obj}",
                    retry_count=retry_count
                )
            completed_results[task_id] = result_item

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}\n{traceback.format_exc()}")
            completed_results[task_id] = ResultItem(
                task_id=task_id,
                status="error",
                result=str(e),
                retry_count=0
            )
        finally:
            semaphore.release()

        # After task completion, update dependents
        for dependent_id in dependents.get(task_id, []):
            if dependent_id not in in_degree:
                continue
            dependencies[dependent_id].discard(task_id)
            in_degree[dependent_id] -= 1
            # If dependency failed, mark dependent as dependency_failed
            if completed_results[task_id].status != "success":
                # Mark dependent as dependency_failed if not already completed
                if dependent_id not in completed_results:
                    completed_results[dependent_id] = ResultItem(
                        task_id=dependent_id,
                        status="dependency_failed",
                        result=f"Dependency {task_id} failed.",
                        retry_count=0
                    )
                    # Remove from graph to avoid scheduling
                    in_degree.pop(dependent_id, None)
                    continue
            # If all dependencies resolved, schedule dependent
            if in_degree.get(dependent_id, 0) == 0 and dependent_id not in completed_results:
                ready_queue.put_nowait(dependent_id)

    active_tasks: Set[asyncio.Task] = set()

    # Initial tasks processing - add tasks with in_degree 0
    while not ready_queue.empty():
        task_id = ready_queue.get_nowait()
        if task_id not in completed_results: # Avoid scheduling if already marked failed
            task_coro = run_task(task_id)
            task_obj = asyncio.create_task(task_coro)
            active_tasks.add(task_obj)
            # Remove task object from set when done to track completion
            task_obj.add_done_callback(active_tasks.discard)

    # Main processing loop: Continue as long as there are active tasks or tasks waiting in the queue
    while active_tasks or not ready_queue.empty():
        # Process newly ready tasks added by completed tasks
        while not ready_queue.empty():
             task_id = ready_queue.get_nowait()
             # Avoid double-scheduling if already completed or running
             # Check completed_results and implicitly check running via active_tasks membership later
             if task_id not in completed_results:
                 # Check if already running (can happen in rare edge cases, though unlikely with this structure)
                 is_running = any(t.get_name() == task_id for t in active_tasks if hasattr(t, 'get_name')) # Check if task is already active
                 if not is_running:
                     task_coro = run_task(task_id)
                     task_obj = asyncio.create_task(task_coro, name=task_id) # Name task for potential check
                     active_tasks.add(task_obj)
                     task_obj.add_done_callback(active_tasks.discard)

        # If queue is empty but tasks are running, wait for one to complete
        # This allows the loop to check the queue again after a task finishes
        if not ready_queue.empty(): # If queue got new items, loop again immediately
             await asyncio.sleep(0) # Yield control briefly
             continue
        elif active_tasks: # If queue is empty but tasks are running
             # Wait for at least one active task to complete
             _, pending = await asyncio.wait(active_tasks, return_when=asyncio.FIRST_COMPLETED)
             # The done_callback handles removing completed tasks from active_tasks
             # Loop will continue, check ready_queue again (potentially populated by completed tasks)
        # If active_tasks is empty AND ready_queue is empty, the loop terminates

    # Any remaining tasks with unresolved dependencies are part of a cycle or blocked
    for task_id in task_map:
        if task_id not in completed_results:
            completed_results[task_id] = ResultItem(
                task_id=task_id,
                status="error",
                result="Unresolved dependencies or cycle detected.",
                retry_count=0
            )

    ordered_responses = [completed_results.get(task.task_id) for task in request.tasks]
    return BatchResponse(responses=ordered_responses)


# --- Example Usage ---

# (Obsolete mock functions removed)


# (Obsolete __main__ example removed)