"""
Local vendored helpers for running multiple Router.acompletion calls concurrently.

This mirrors the proposed litellm `router_utils/parallel_acompletion.py` API
so our code can adopt the pattern without depending on an unmerged upstream PR.

Exports:
- RouterParallelRequest
- RouterParallelResult
- gather_parallel_acompletions
- iter_parallel_acompletions
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


async def gather_parallel_acompletions(
    router: Any,
    requests: List[RouterParallelRequest],
    *,
    concurrency: int = 8,
    return_exceptions: bool = True,
    preserve_order: bool = False,
    batch_id: Optional[str] = None,
) -> List[RouterParallelResult]:
    if concurrency <= 0:
        raise ValueError("concurrency must be >= 1")
    sem = asyncio.Semaphore(concurrency)
    batch_id = batch_id or uuid.uuid4().hex
    tasks: List[asyncio.Task[RouterParallelResult]] = [
        asyncio.create_task(_run_one(router, sem, i, r, return_exceptions, batch_id))
        for i, r in enumerate(requests)
    ]
    try:
        results = await asyncio.gather(*tasks, return_exceptions=False)
    except BaseException:
        for t in tasks:
            t.cancel()
        with contextlib.suppress(Exception):
            await asyncio.gather(*tasks, return_exceptions=True)
        raise
    if preserve_order:
        results.sort(key=lambda r: r.index)
    return results


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


async def iter_parallel_acompletions(
    router: Any,
    requests: List[RouterParallelRequest],
    *,
    concurrency: int = 8,
    return_exceptions: bool = True,
) -> AsyncIterator[RouterParallelResult]:
    if concurrency <= 0:
        raise ValueError("concurrency must be >= 1")
    queue: "asyncio.Queue[Any]" = asyncio.Queue()
    worker = asyncio.create_task(
        _iter_worker(router, requests, concurrency, return_exceptions, queue)
    )
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, BaseException):
                raise item
            yield item
    finally:
        worker.cancel()
        with contextlib.suppress(Exception):
            await worker


__all__ = [
    "RouterParallelRequest",
    "RouterParallelResult",
    "gather_parallel_acompletions",
    "iter_parallel_acompletions",
]
