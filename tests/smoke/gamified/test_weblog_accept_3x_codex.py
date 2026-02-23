import os
import sys
import json
import urllib.request
from pathlib import Path


def _run(cmd: str) -> int:
    return os.system(cmd)


def _latest_run_id() -> str:
    runs = sorted(Path("workspace/runs").glob("*/instances"))
    return runs[-1].parent.name if runs else ""


def _http_get(url: str, timeout: int = 5):
    return urllib.request.urlopen(url, timeout=timeout)


def _http_post(url: str, payload: dict, timeout: int = 5):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    return urllib.request.urlopen(req, timeout=timeout)


def test_weblog_accept_3x_codex(tmp_path: Path):
    # 3 variants, autostart backend on a free port, Codex-run
    prompt = tmp_path / "prompt_web3.md"
    prompt.write_text(
        "\n".join(
            [
                "## Gamified Run Spec — Web Accept 3x",
                "## Codebase",
                "repo_root: .",
                "## Approaches",
                "- name: mul_shift_add",
                "- name: mul_karatsuba",
                "- name: mul_chunked",
                "## Runner",
                "type: python_benchmark",
                "entry: prototypes/gamified/bench/multiply_benchmark.py",
                "create_if_missing: true",
                "## Execution",
                "max_iters: 1",
                "api_base: http://127.0.0.1",
            ]
        )
    )

    cmd = (
        "GAMIFIED_FAST_BENCH=1 PYTHONPATH=./src "
        + sys.executable
        + " -m prototypes.gamified.cli run --codebase . "
        + f"--prompt-file {prompt.as_posix()} "
        + "--instances 3 --autostart-backend --no-start-dashboard"
    )
    rc = _run(cmd)
    assert rc == 0

    rid = _latest_run_id()
    assert rid, "no run created"
    run_root = Path("workspace/runs") / rid
    # Scorecard with winner
    sc = run_root / "scorecard.json"
    assert sc.exists(), "missing scorecard.json"
    js = json.loads(sc.read_text())
    assert js.get("winner"), "winner not set"
    for v in ("mul_shift_add", "mul_karatsuba", "mul_chunked"):
        assert v in (js.get("approaches") or {}), f"missing approach {v}"

    # Backend base URL (chosen free port)
    api_file = run_root / "api_base.txt"
    assert api_file.exists(), "missing api_base.txt"
    api_base = api_file.read_text().strip()
    # Proto dashboard up
    r = _http_get(f"{api_base}/proto/dashboard", timeout=5)
    assert 200 <= getattr(r, "status", 200) < 500

    # Ingest round-trip (log + episode) should return ok even without DB
    rl = _http_post(
        f"{api_base}/ingest/log",
        {
            "ts": 0.0,
            "run_id": rid,
            "variant": "acceptance_probe",
            "episode_id": None,
            "stream": "app",
            "level": "INFO",
            "source": "accept_smoke",
            "message": "probe",
            "meta": {},
        },
        timeout=5,
    )
    assert json.loads(rl.read().decode("utf-8")).get("ok") is True
    re = _http_post(
        f"{api_base}/ingest/episode",
        {
            "ts": 0.0,
            "run_id": rid,
            "episode_id": "probe-1",
            "variant": "acceptance_probe",
            "pass": True,
            "score": 1.0,
            "metrics": {},
            "error_count": 0,
            "screenshots": [],
        },
        timeout=5,
    )
    assert json.loads(re.read().decode("utf-8")).get("ok") is True
