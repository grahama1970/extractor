#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
from __future__ import annotations

from pathlib import Path

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


def main() -> int:
    codex_home = Path.home() / ".codex"
    auth_path = codex_home / "auth.json"
    mode = _auth_store_mode(codex_home)
    if mode == "file":
        if not auth_path.exists():
            raise SystemExit(
                f"Codex auth missing at {auth_path}. Run `codex login` (OAuth) first."
            )
        print(f"OK: Codex auth file present at {auth_path}")
    else:
        print(
            f"OK: Codex auth store mode is '{mode}'. No auth.json required."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
