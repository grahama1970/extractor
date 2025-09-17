from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
import uuid

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None  # type: ignore
# NVML (GPU) support optional
try:
    import pynvml  # type: ignore

    _nvml_ok = True
    try:
        pynvml.nvmlInit()
    except Exception:
        _nvml_ok = False
except Exception:  # pragma: no cover
    pynvml = None  # type: ignore
    _nvml_ok = False


def get_run_id() -> str:
    return uuid.uuid4().hex


def iso_now() -> str:
    return datetime.now().isoformat()


def make_event(
    stage: str,
    severity: str,
    code: str,
    message: str,
    context: Optional[Dict[str, Any]] = None,
    ts: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "stage": stage,
        "severity": severity,
        "code": code,
        "message": message,
        "ts": ts or iso_now(),
        "context": context or {},
    }


def snapshot_resources(prefix: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    try:
        if psutil is not None:
            proc = psutil.Process()
            out[f"proc_rss_mb_{prefix}"] = int((proc.memory_info().rss or 0) / (1024 * 1024))
            vm = psutil.virtual_memory()
            out[f"vmem_used_mb_{prefix}"] = int((getattr(vm, "used", 0)) / (1024 * 1024))
        if _nvml_ok and pynvml is not None:
            try:
                dev_count = pynvml.nvmlDeviceGetCount()
                gpumem = []
                util = []
                for i in range(dev_count):
                    h = pynvml.nvmlDeviceGetHandleByIndex(i)
                    mem = pynvml.nvmlDeviceGetMemoryInfo(h)
                    u = pynvml.nvmlDeviceGetUtilizationRates(h)
                    gpumem.append(int(mem.used / (1024 * 1024)))
                    util.append(int(getattr(u, "gpu", 0)))
                out[f"gpu_mem_used_mb_{prefix}"] = gpumem
                out[f"gpu_util_percent_{prefix}"] = util
            except Exception:
                pass
    except Exception:
        pass
    return out


def build_stage_timings(
    stage_start_ts: str, t0_monotonic: float, extra: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    import time

    timings = {
        "stage_start_ts": stage_start_ts,
        "stage_end_ts": iso_now(),
        "stage_duration_ms": int((time.monotonic() - t0_monotonic) * 1000),
    }
    if extra:
        timings.update(extra)
    return timings


# Optional background resource sampler (CPU/RSS/VMem)
import threading, time as _time


def start_resource_sampler(interval_sec: float = 2.0):
    """Start a background sampler that periodically records process/system metrics.
    Returns a sampler dict with 'thread' and 'samples'. If psutil not available, returns None.
    """
    if psutil is None or interval_sec <= 0:
        return None
    samples = []
    stop_flag = {"stop": False}

    def _run():
        while not stop_flag["stop"]:
            try:
                proc = psutil.Process()
                vm = psutil.virtual_memory()
                gpu_mem = None
                gpu_util = None
                try:
                    if _nvml_ok and pynvml is not None:
                        h = pynvml.nvmlDeviceGetHandleByIndex(0)
                        mem = pynvml.nvmlDeviceGetMemoryInfo(h)
                        u = pynvml.nvmlDeviceGetUtilizationRates(h)
                        gpu_mem = int(mem.used / (1024 * 1024))
                        gpu_util = int(getattr(u, "gpu", 0))
                except Exception:
                    pass
                samples.append(
                    {
                        "ts": iso_now(),
                        "proc_rss_mb": int((proc.memory_info().rss or 0) / (1024 * 1024)),
                        "cpu_percent": float(proc.cpu_percent(interval=None)),
                        "vmem_used_mb": int((getattr(vm, "used", 0)) / (1024 * 1024)),
                        "gpu_mem_used_mb": gpu_mem,
                        "gpu_util_percent": gpu_util,
                    }
                )
            except Exception:
                pass
            _time.sleep(interval_sec)

    th = threading.Thread(target=_run, daemon=True)
    th.start()
    return {"thread": th, "samples": samples, "stop": stop_flag}


def stop_resource_sampler(sampler):
    """Stop the background sampler and return collected samples."""
    try:
        if sampler and isinstance(sampler, dict):
            sampler["stop"]["stop"] = True
            th = sampler.get("thread")
            if th:
                th.join(timeout=1.0)
            return sampler.get("samples", [])
    except Exception:
        return []
    return []


def classify_llm_error(exc: Exception) -> dict:
    """Normalize LLM exceptions to a stable code/category/message."""
    msg = str(exc)
    low = msg.lower()
    if any(k in low for k in ("timeout", "readtimeout", "timed out")):
        return {"code": "llm_timeout", "category": "timeout", "message": msg}
    if any(k in low for k in ("network", "connect", "connection", "econn", "dns", "proxy")):
        return {"code": "llm_network_error", "category": "network", "message": msg}
    return {"code": "llm_batch_failed", "category": "general", "message": msg}


def gpu_metrics_available() -> bool:
    """Return True if NVML GPU metrics are available."""
    return bool(globals().get("_nvml_ok", False))
