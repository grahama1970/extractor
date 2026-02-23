from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol, Dict, Type

from .env_utils import ROOT, env_with_pythonpath

try:  # py311+
    import tomllib  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


def _auth_store_mode(codex_home: Path) -> str:
    config_path = codex_home / "config.toml"
    if not config_path.exists():
        return "auto"
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return "auto"
    value = data.get("cli_auth_credentials_store")
    if not value:
        return "auto"
    return str(value).strip().lower()


def _ensure_codex_auth(env: dict) -> None:
    codex_home = Path(env.get("CODEX_HOME") or Path.home() / ".codex")
    mode = _auth_store_mode(codex_home)
    auth_path = codex_home / "auth.json"
    if mode == "file" and not auth_path.exists():
        raise RuntimeError(f"Codex OAuth auth file missing: {auth_path}. Run `codex login` first.")


@dataclass(frozen=True)
class RunHandle:
    thread_id: str | None
    log_path: Path
    output_path: Path


class AgentRunner(Protocol):
    name: str

    def start(
        self,
        prompt: str,
        *,
        schema_path: Path,
        output_path: Path,
        log_path: Path,
        model: Optional[str] = None,
        timeout_sec: Optional[int] = None,
    ) -> RunHandle: ...

    def resume(
        self,
        handle: RunHandle,
        prompt: str,
        *,
        schema_path: Path,
        output_path: Path,
        log_path: Path,
        model: Optional[str] = None,
        timeout_sec: Optional[int] = None,
    ) -> RunHandle: ...


def _extract_thread_id(log_path: Path) -> str | None:
    try:
        for line in log_path.read_text(encoding="utf-8").splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                if "thread_id" in payload:
                    return str(payload["thread_id"])
                data = payload.get("data") or payload.get("thread") or {}
                if isinstance(data, dict) and data.get("id"):
                    return str(data["id"])
    except OSError:
        return None
    return None


class BaseSubprocessRunner:
    """Shared logic for streaming subprocess I/O."""

    @staticmethod
    def _stream(pipe, log_handle, out_handle=None) -> None:
        if pipe is None:
            return
        for line in iter(pipe.readline, ""):
            if not line:
                break
            if out_handle:
                out_handle.write(line)
                out_handle.flush()
            log_handle.write(line)
        log_handle.flush()
        pipe.close()

    @staticmethod
    def _sanitize_json(text: str) -> str:
        """Strip markdown code fences from JSON output."""
        text = text.strip()
        # Handle text before code fence (e.g., "Some explanation:\n```json\n{...}\n```")
        fence_start = text.find("```")
        if fence_start > 0:
            text = text[fence_start:]
        if text.startswith("```"):
            # Find first newline after fence
            nl = text.find("\n")
            if nl != -1:
                text = text[nl + 1 :]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    def _execute(
        self,
        cmd: list[str],
        prompt: str,
        log_path: Path,
        output_path: Path,
        timeout: Optional[int],
        env: Optional[dict] = None,
        cwd: Optional[Path] = None,
    ) -> None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if env is None:
            env = os.environ.copy()
        if cwd is None:
            cwd = ROOT

        with log_path.open("w", encoding="utf-8") as log_file:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                cwd=cwd,
            )
            if proc.stdin is None:
                raise RuntimeError(f"Failed to open stdin for {cmd[0]}")

            proc.stdin.write(prompt)
            proc.stdin.close()

            stdout_thread = threading.Thread(
                target=self._stream, args=(proc.stdout, log_file, sys.stdout), daemon=True
            )
            stderr_thread = threading.Thread(
                target=self._stream, args=(proc.stderr, log_file, sys.stderr), daemon=True
            )
            stdout_thread.start()
            stderr_thread.start()
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                stdout_thread.join()
                stderr_thread.join()
                raise RuntimeError(f"{cmd[0]} timed out after {timeout}s (log: {log_path})")
            stdout_thread.join()
            stderr_thread.join()

            if proc.returncode != 0:
                raise RuntimeError(f"{cmd[0]} failed (rc={proc.returncode})")


class CodexRunner(BaseSubprocessRunner):
    name = "codex"

    def _run(
        self,
        cmd: list[str],
        prompt: str,
        *,
        schema_path: Path,
        output_path: Path,
        log_path: Path,
        model: Optional[str],
        timeout_sec: Optional[int],
    ) -> RunHandle:
        full_cmd = cmd + [
            "--json",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "-C",
            str(ROOT),
        ]
        if model:
            full_cmd.extend(["--model", model])

        timeout = timeout_sec
        if timeout is None:
            raw = os.environ.get("CONTRACT_LOOP_CODEX_TIMEOUT_SEC", "600")
            try:
                timeout = int(raw)
            except ValueError:
                timeout = 600
        if timeout is not None and timeout <= 0:
            timeout = None

        env = env_with_pythonpath()
        env.setdefault("CODEX_HOME", str(Path.home() / ".codex"))
        env.setdefault("CODEX_CONTEXT_DISABLE", "1")
        _ensure_codex_auth(env)

        super()._execute(full_cmd, prompt, log_path, output_path, timeout, env=env)

        thread_id = _extract_thread_id(log_path)
        return RunHandle(thread_id=thread_id, log_path=log_path, output_path=output_path)

    def start(
        self,
        prompt: str,
        *,
        schema_path: Path,
        output_path: Path,
        log_path: Path,
        model: Optional[str] = None,
        timeout_sec: Optional[int] = None,
    ) -> RunHandle:
        cmd = ["codex", "exec"]
        return self._run(
            cmd,
            prompt,
            schema_path=schema_path,
            output_path=output_path,
            log_path=log_path,
            model=model,
            timeout_sec=timeout_sec,
        )

    def resume(
        self,
        handle: RunHandle,
        prompt: str,
        *,
        schema_path: Path,
        output_path: Path,
        log_path: Path,
        model: Optional[str] = None,
        timeout_sec: Optional[int] = None,
    ) -> RunHandle:
        if not handle.thread_id:
            raise RuntimeError("Cannot resume: thread_id not found in prior run log")
        cmd = ["codex", "exec", "resume", handle.thread_id]
        return self._run(
            cmd,
            prompt,
            schema_path=schema_path,
            output_path=output_path,
            log_path=log_path,
            model=model,
            timeout_sec=timeout_sec,
        )


class ClaudeRunner(BaseSubprocessRunner):
    """Runner for `claude -p`."""

    name = "claude"

    def _run(
        self,
        prompt: str,
        log_path: Path,
        output_path: Path,
        model: Optional[str],
        timeout_sec: Optional[int],
    ) -> RunHandle:
        cmd = [
            "claude",
            "-p",
            prompt,
            "--output-format",
            "json",
            "--dangerously-skip-permissions",
        ]
        if model:
            cmd.extend(["--model", model])

        timeout = timeout_sec or 600

        # Clear env vars that interfere with OAuth-based headless mode
        env = os.environ.copy()
        for key in [
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_AUTH_TOKEN",
            "ANTHROPIC_BASE_URL",
            "ANTHROPIC_API_BASE",
            "ANTHROPIC_ORG_ID",
            "CLAUDE_API_KEY",
            "CLAUDE_AUTH_TOKEN",
            "CLAUDE_CODE_API_KEY",
        ]:
            env.pop(key, None)

        super()._execute(cmd, "", log_path, output_path, timeout, env=env)

        # Post-process: extract result from JSON output
        if log_path.exists():
            text = log_path.read_text(encoding="utf-8")
            # Claude --output-format json returns {"result": "..."}
            # Try to extract the inner result
            try:
                import json as _json

                data = _json.loads(text)
                if isinstance(data, dict) and "result" in data:
                    output_path.write_text(data["result"], encoding="utf-8")
                else:
                    output_path.write_text(text, encoding="utf-8")
            except Exception:
                clean_json = BaseSubprocessRunner._sanitize_json(text)
                output_path.write_text(clean_json, encoding="utf-8")

        return RunHandle(thread_id=None, log_path=log_path, output_path=output_path)

    def start(
        self,
        prompt: str,
        *,
        schema_path: Path,
        output_path: Path,
        log_path: Path,
        model: Optional[str] = None,
        timeout_sec: Optional[int] = None,
    ) -> RunHandle:
        return self._run(prompt, log_path, output_path, model, timeout_sec)

    def resume(
        self,
        handle: RunHandle,  # noqa: ARG002 - ignored, Claude is stateless
        prompt: str,
        *,
        schema_path: Path,
        output_path: Path,
        log_path: Path,
        model: Optional[str] = None,
        timeout_sec: Optional[int] = None,
    ) -> RunHandle:
        # Claude -p is stateless, so resume == start with new prompt
        return self._run(prompt, log_path, output_path, model, timeout_sec)


class OpenCodeRunner(BaseSubprocessRunner):
    """Runner for `opencode run ...`."""

    name = "opencode"

    def _run(
        self,
        prompt: str,
        log_path: Path,
        output_path: Path,
        model: Optional[str],
        timeout_sec: Optional[int],
    ) -> RunHandle:
        cmd = ["opencode", "run", prompt, "--format", "json"]
        if model:
            cmd.extend(["--model", model])

        timeout = timeout_sec or 600
        env = os.environ.copy()

        super()._execute(cmd, "", log_path, output_path, timeout, env=env)

        if log_path.exists():
            text = log_path.read_text(encoding="utf-8")
            clean_json = BaseSubprocessRunner._sanitize_json(text)
            output_path.write_text(clean_json, encoding="utf-8")

        return RunHandle(thread_id=None, log_path=log_path, output_path=output_path)

    def start(
        self,
        prompt: str,
        *,
        schema_path: Path,
        output_path: Path,
        log_path: Path,
        model: Optional[str] = None,
        timeout_sec: Optional[int] = None,
    ) -> RunHandle:
        return self._run(prompt, log_path, output_path, model, timeout_sec)

    def resume(self, *args, **kwargs) -> RunHandle:
        return self.start(*args, **kwargs)


class GenericRunner(BaseSubprocessRunner):
    """
    Runner that uses CONTRACT_LOOP_GENERIC_CMD template.
    Example: my-tool --input {prompt_file} --output {output_file}
    """

    name = "generic"

    def _run(
        self,
        prompt: str,
        log_path: Path,
        output_path: Path,
        model: Optional[str],
        timeout_sec: Optional[int],
    ) -> RunHandle:
        cmd_template = os.environ.get("CONTRACT_LOOP_GENERIC_CMD")
        if not cmd_template:
            raise RuntimeError("CONTRACT_LOOP_GENERIC_CMD env var not set")

        prompt_file = log_path.with_suffix(".prompt")
        prompt_file.write_text(prompt, encoding="utf-8")

        cmd_str = cmd_template.format(
            prompt=shlex.quote(prompt),
            prompt_file=str(prompt_file),
            output_file=str(output_path),
            model=model or "",
        )

        cmd = shlex.split(cmd_str)
        timeout = timeout_sec or 600
        env = os.environ.copy()

        super()._execute(cmd, "", log_path, output_path, timeout, env=env)

        if not output_path.exists() and log_path.exists():
            output_path.write_text(log_path.read_text(), encoding="utf-8")

        return RunHandle(thread_id=None, log_path=log_path, output_path=output_path)

    def start(
        self,
        prompt: str,
        *,
        schema_path: Path,
        output_path: Path,
        log_path: Path,
        model: Optional[str] = None,
        timeout_sec: Optional[int] = None,
    ) -> RunHandle:
        return self._run(prompt, log_path, output_path, model, timeout_sec)

    def resume(self, *args, **kwargs) -> RunHandle:
        return self.start(*args, **kwargs)


class AgentFactory:
    _runners: Dict[str, Type[AgentRunner]] = {
        "codex": CodexRunner,
        "claude": ClaudeRunner,
        "opencode": OpenCodeRunner,
        "generic": GenericRunner,
    }

    @classmethod
    def create(cls, name: str) -> AgentRunner:
        name = name.lower()
        if name not in cls._runners:
            raise ValueError(f"Unknown runner: {name}. Available: {list(cls._runners.keys())}")

        runner_cls = cls._runners[name]
        return runner_cls()  # type: ignore


__all__ = [
    "AgentRunner",
    "CodexRunner",
    "ClaudeRunner",
    "OpenCodeRunner",
    "GenericRunner",
    "AgentFactory",
    "RunHandle",
]
