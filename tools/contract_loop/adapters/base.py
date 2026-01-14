from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from ..utils import ContractLoopError


@dataclass(frozen=True)
class AdapterContext:
    """Shared context passed to adapter helpers."""

    out_dir: Path


class BaseAdapter:
    name = "base"

    def build_steps(self, _args, _fixture):  # pragma: no cover - interface only
        raise NotImplementedError

    def clean_downstream(
        self,
        out: Path,
        steps: Sequence,
        start_index: int,
        _index_by_name: dict[str, int],
    ) -> None:
        """Default cleanup: delete output_paths under out for downstream steps."""
        import shutil

        for step in steps[start_index:]:
            for rel in step.output_paths:
                target = out / rel
                if target.is_dir():
                    shutil.rmtree(target, ignore_errors=True)
                elif target.exists():
                    try:
                        target.unlink()
                    except Exception:
                        pass
            visuals_link = out / "visuals" / step.name
            if visuals_link.exists() or visuals_link.is_symlink():
                if visuals_link.is_symlink() or visuals_link.is_file():
                    try:
                        visuals_link.unlink()
                    except Exception:
                        pass
                else:
                    shutil.rmtree(visuals_link, ignore_errors=True)

    def verify_fixture_step(self, _step_name: str, _out: Path, _fixture: dict) -> None:
        return

    def collect_llm_samples(self, _step_name: str, _out: Path, _fixture: dict) -> list[str]:
        return []

    def questions_for_step(self, _step_name: str) -> Iterable[str]:
        return ["What specific contract check is failing?"]

    def verify_visuals(
        self,
        _step_name: str,
        _out: Path,
        _args: Any,
        _fixture: dict | None,
    ) -> None:
        return


def raise_adapter_error(message: str) -> None:
    raise ContractLoopError(message)
