"""
DEPRECATED: Use `scillm.Router.parallel_acompletions` directly.

This module previously provided a local parallel `acompletion` orchestration. To
avoid bespoke logic, pipeline stages should import and use the official
`Router.parallel_acompletions` from SciLLM. This file remains temporarily to
avoid import errors; no new code should depend on it.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional


@dataclass
class RouterParallelRequest:
    model: str
    messages: List[Dict[str, Any]]
    kwargs: Optional[Dict[str, Any]] = None


@dataclass
class RouterParallelResult:
    index: int
    request: RouterParallelRequest
    response: Optional[Any] = None
    exception: Optional[BaseException] = None


async def _run_one(
    router: Any,
    sem: asyncio.Semaphore,
    idx: int,
    req: RouterParallelRequest,
    return_exceptions: bool,
    batch_id: str,
) -> RouterParallelResult:
    async with sem:
        try:
            merged_kwargs = dict(req.kwargs or {})
            meta_extra = {"parallel_batch_id": batch_id, "parallel_index": idx}
            existing_meta = merged_kwargs.get("metadata")
            if isinstance(existing_meta, dict):
                merged_meta = {**existing_meta, **meta_extra}
            else:
                merged_meta = meta_extra
            merged_kwargs["metadata"] = merged_meta

            resp = await router.acompletion(
                model=req.model,
                messages=req.messages,
                **merged_kwargs,
            )
            return RouterParallelResult(index=idx, request=req, response=resp)
        except BaseException as e:
            if not return_exceptions:
                raise
            return RouterParallelResult(index=idx, request=req, exception=e)


async def gather_parallel_acompletions(*args, **kwargs):  # pragma: no cover
    raise RuntimeError(
        "vendor_parallel_acompletion is deprecated. Use scillm.Router.parallel_acompletions instead."
    )


async def _iter_worker(
    router: Any,
    requests: List[RouterParallelRequest],
    concurrency: int,
    return_exceptions: bool,
    queue: "asyncio.Queue[Any]",
):
    sem = asyncio.Semaphore(concurrency)
    batch_id = uuid.uuid4().hex
    tasks = [
        asyncio.create_task(_run_one(router, sem, i, r, return_exceptions, batch_id))
        for i, r in enumerate(requests)
    ]
    try:
        for fut in asyncio.as_completed(tasks):
            try:
                res = await fut
                await queue.put(res)
            except BaseException as e:
                for t in tasks:
                    t.cancel()
                await queue.put(e)
                return
    finally:
        await queue.put(None)


async def iter_parallel_acompletions(*args, **kwargs):  # pragma: no cover
    raise RuntimeError(
        "vendor_parallel_acompletion is deprecated. Use scillm.Router.parallel_acompletions instead."
    )


__all__ = [
    "RouterParallelRequest",
    "RouterParallelResult",
    "gather_parallel_acompletions",
    "iter_parallel_acompletions",
]
