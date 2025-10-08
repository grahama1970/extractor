from __future__ import annotations
import os, json, subprocess, time
from dataclasses import dataclass, asdict
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

try:
    import psutil  # type: ignore
except Exception:
    psutil = None

# NVML optional
try:
    import pynvml  # type: ignore
    _NVML_OK = True
except Exception:
    _NVML_OK = False


@dataclass
class GPUTelemetry:
    present: bool
    name: Optional[str] = None
    total_mb: Optional[int] = None
    free_mb: Optional[int] = None
    used_mb: Optional[int] = None
    memory_util: Optional[float] = None  # fraction 0..1


@dataclass
class CPUTelemetry:
    logical_cores: Optional[int] = None
    load_avg_1: Optional[float] = None
    rss_mb: Optional[int] = None
    avail_mem_mb: Optional[int] = None


@dataclass
class AdaptiveConfig:
    detection_batch: int
    recognition_batch: int
    table_batch: int
    layout_batch: int
    device: str
    mem_guard_ratio: float
    reason: str
    table_workers: int
    figure_concurrency: int


HISTORY_FILENAME = "adaptive_history.json"


def _nvml_gpu_telemetry() -> GPUTelemetry:
    if not _NVML_OK:
        return GPUTelemetry(False)
    try:
        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        info = pynvml.nvmlDeviceGetMemoryInfo(h)
        name = pynvml.nvmlDeviceGetName(h).decode("utf-8", "ignore")
        total = int(info.total / (1024 * 1024))
        free = int(info.free / (1024 * 1024))
        used = int(info.used / (1024 * 1024))
        util = used / total if total else None
        return GPUTelemetry(True, name, total, free, used, util)
    except Exception:
        # Fallback to nvidia-smi path below
        return _fallback_nvidia_smi()


def _fallback_nvidia_smi() -> GPUTelemetry:
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=memory.total,memory.used,memory.free,name",
                "--format=csv,noheader,nounits",
            ],
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).decode().strip().splitlines()
        if not out:
            return GPUTelemetry(False)
        parts = [p.strip() for p in out[0].split(",")]
        if len(parts) < 4:
            return GPUTelemetry(False)
        total, used, free, name = parts
        total_i = int(total)
        used_i = int(used)
        free_i = int(free)
        util = used_i / total_i if total_i else None
        return GPUTelemetry(True, name, total_i, free_i, used_i, util)
    except Exception:
        return GPUTelemetry(False)


def _cpu_telemetry() -> CPUTelemetry:
    if psutil is None:
        return CPUTelemetry()
    try:
        load = psutil.getloadavg()[0] if hasattr(psutil, "getloadavg") else None
    except Exception:
        load = None
    try:
        rss_mb = int(psutil.Process().memory_info().rss / (1024 * 1024))
    except Exception:
        rss_mb = None
    try:
        avail_mem_mb = int(psutil.virtual_memory().available / (1024 * 1024))
    except Exception:
        avail_mem_mb = None
    return CPUTelemetry(
        logical_cores=psutil.cpu_count(logical=True) if psutil else None,
        load_avg_1=load,
        rss_mb=rss_mb,
        avail_mem_mb=avail_mem_mb,
    )


def _derive_adaptive_batches(*, gpu: GPUTelemetry, mem_guard_ratio: float) -> Dict[str, int]:
    """Simple heuristic to pick batch sizes from free VRAM."""
    if not gpu.present or not gpu.free_mb:
        return dict(detection=2, recognition=2, table=2, layout=2)
    if gpu.free_mb < 2000:
        return dict(detection=1, recognition=1, table=1, layout=1)
    free_budget = gpu.free_mb * mem_guard_ratio * 0.7

    def _calc(budget, per_sample):
        return max(1, min(8, int(budget / per_sample)))

    return dict(
        detection=_calc(free_budget * 0.30, 35),
        recognition=_calc(free_budget * 0.25, 18),
        table=_calc(free_budget * 0.20, 25),
        layout=_calc(free_budget * 0.25, 20),
    )


def load_history(root: Path) -> Dict[str, Any]:
    hp = root / HISTORY_FILENAME
    if not hp.exists():
        return {"runs": []}
    try:
        return json.loads(hp.read_text())
    except Exception:
        return {"runs": []}


def save_history(root: Path, hist: Dict[str, Any]) -> None:
    try:
        hp = root / HISTORY_FILENAME
        hp.write_text(json.dumps(hist, indent=2))
    except Exception:
        pass


def _adjust_with_history(
    auto: Dict[str, int],
    history: Dict[str, Any],
    *,
    target_low: float,
    target_high: float,
) -> Dict[str, int]:
    runs: List[Dict[str, Any]] = history.get("runs", [])[-5:]
    if not runs:
        return auto
    utils = [r.get("gpu_util") for r in runs if isinstance(r.get("gpu_util"), (int, float))]
    if not utils:
        return auto
    avg_util = sum(utils) / len(utils)
    adjusted = dict(auto)
    if avg_util < target_low:
        for k in adjusted:
            adjusted[k] = min(8, adjusted[k] + 1)
    elif avg_util > target_high:
        for k in adjusted:
            adjusted[k] = max(1, adjusted[k] - 1)
    return adjusted


def _derive_table_workers(cpu: CPUTelemetry, explicit: Optional[str]) -> int:
    if explicit:
        try:
            return max(1, int(explicit))
        except Exception:
            pass
    cores = cpu.logical_cores or 8
    return max(2, min(8, cores // 3))


def _derive_figure_concurrency(cpu: CPUTelemetry, gpu: GPUTelemetry, explicit: Optional[str]) -> int:
    if explicit:
        try:
            return max(1, int(explicit))
        except Exception:
            pass
    if gpu.present:
        return 4 if (cpu.logical_cores or 8) >= 8 else 2
    return 2


def build_adaptive_config(output_dir: Path, *, mem_guard_ratio: float = 0.85) -> AdaptiveConfig:
    gpu = _nvml_gpu_telemetry()
    cpu = _cpu_telemetry()

    explicit = {
        "detection": os.getenv("STAGE02_DETECTION_BATCH"),
        "recognition": os.getenv("STAGE02_RECOGNITION_BATCH"),
        "table": os.getenv("STAGE02_TABLE_BATCH"),
        "layout": os.getenv("STAGE02_LAYOUT_BATCH"),
        "device": os.getenv("STAGE02_DEVICE"),
        "table_workers": os.getenv("STAGE05_WORKERS"),
        "figure_concurrency": os.getenv("STAGE06_CONCURRENCY"),
    }

    history = load_history(output_dir if output_dir.exists() else Path("."))
    auto = _derive_adaptive_batches(gpu=gpu, mem_guard_ratio=mem_guard_ratio)

    # Cross-document adjustment
    target_low = float(os.getenv("ADAPTIVE_TARGET_UTIL_LOW", "0.55"))
    target_high = float(os.getenv("ADAPTIVE_TARGET_UTIL_HIGH", "0.88"))
    auto = _adjust_with_history(auto, history, target_low=target_low, target_high=target_high)

    cfg = AdaptiveConfig(
        detection_batch=int(explicit["detection"] or auto["detection"]),
        recognition_batch=int(explicit["recognition"] or auto["recognition"]),
        table_batch=int(explicit["table"] or auto["table"]),
        layout_batch=int(explicit["layout"] or auto["layout"]),
        device=(explicit["device"] or ("cuda" if gpu.present else "cpu")),
        mem_guard_ratio=mem_guard_ratio,
        reason=
            "explicit_env_override"
            if any(explicit[k] for k in ["detection", "recognition", "table", "layout", "device"])
            else ("adaptive_history" if history.get("runs") else "adaptive_telemetry"),
        table_workers=_derive_table_workers(cpu, explicit["table_workers"]),
        figure_concurrency=_derive_figure_concurrency(cpu, gpu, explicit["figure_concurrency"]),
    )

    # Persist telemetry + chosen config
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "gpu": asdict(gpu),
        "cpu": asdict(cpu),
        "config": asdict(cfg),
    }
    try:
        out = (
            output_dir / "json_output"
            if output_dir.name == "02_marker_extractor"
            else output_dir / "02_marker_extractor" / "json_output"
        )
        out.mkdir(parents=True, exist_ok=True)
        (out / "02_adaptive_config.json").write_text(json.dumps(payload, indent=2))
    except Exception:
        pass
    return cfg


def start_gpu_sampler(interval_sec: float = 1.0):
    """Start a background sampler for GPU memory utilization; returns a handle with stop() and peak()."""
    tel = _nvml_gpu_telemetry()
    if not tel.present:
        tel = _fallback_nvidia_smi()
    if not tel.present:
        return None

    state = {"peak": 0.0, "stop": False}

    def _sample_loop():
        while not state["stop"]:
            t = _nvml_gpu_telemetry()
            if not t.present:
                t = _fallback_nvidia_smi()
            util = t.memory_util or 0.0
            if util and util > state["peak"]:
                state["peak"] = util
            time.sleep(max(0.1, interval_sec))

    th = threading.Thread(target=_sample_loop, daemon=True)
    th.start()

    class _Handle:
        def stop(self):
            state["stop"] = True
            try:
                th.join(timeout=2)
            except Exception:
                pass

        def peak(self) -> Optional[float]:
            return state.get("peak")

    return _Handle()


def finalize_adaptive_run(
    output_dir: Path,
    *,
    success: bool,
    oom_retry: bool,
    cfg: AdaptiveConfig,
    gpu_end_util: Optional[float] = None,
    gpu_peak_util: Optional[float] = None,
) -> None:
    try:
        root = output_dir
        hist = load_history(root)
        runs = hist.get("runs", [])
        runs.append(
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "gpu_end_util": gpu_end_util,
                "gpu_peak_util": gpu_peak_util,
                "success": success,
                "oom_retry": oom_retry,
                "cfg": {
                    "d": cfg.detection_batch,
                    "r": cfg.recognition_batch,
                    "t": cfg.table_batch,
                    "l": cfg.layout_batch,
                },
            }
        )
        hist["runs"] = runs[-50:]
        save_history(root, hist)
    except Exception:
        pass
