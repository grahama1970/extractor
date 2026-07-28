"""Dependency and import-boundary contracts for the base extraction lane."""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_BASE_DEPS = {
    "anthropic",
    "faiss-cpu",
    "fetcher",
    "google-genai",
    "litellm",
    "nvidia-ml-py",
    "openai",
    "python-arango",
    "redis",
    "scillm",
    "sentence-transformers",
    "pymupdf",
    "pymupdf-layout",
}
FORBIDDEN_ACTIVE_IMPORTS = {
    "anthropic",
    "arango",
    "faiss",
    "fetcher",
    "fitz",
    "google",
    "litellm",
    "openai",
    "pymupdf",
    "redis",
    "scillm",
    "sentence_transformers",
}
ACTIVE_BASE_FILES = [
    ROOT / "src/extractor/cli_app.py",
    ROOT / "src/extractor/application/extract_file.py",
    ROOT / "src/extractor/application/status.py",
    ROOT / "src/extractor/core/providers/registry.py",
    ROOT / "src/extractor/integrations/tau.py",
]


def _package_name(requirement: str) -> str:
    return (
        requirement.split("@", 1)[0]
        .split("[", 1)[0]
        .split("<", 1)[0]
        .split(">", 1)[0]
        .split("=", 1)[0]
        .strip()
    )


def _top_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", 1)[0])
    return imports


def test_base_dependencies_exclude_provider_database_and_regression_engines() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    base_deps = {_package_name(dep) for dep in data["project"]["dependencies"]}

    assert not (base_deps & FORBIDDEN_BASE_DEPS)
    extras = data["project"]["optional-dependencies"]
    provider_deps = {_package_name(dep) for dep in extras["providers"]}
    assert {"scillm", "fetcher", "python-arango", "redis"} <= provider_deps
    regression_deps = {_package_name(dep) for dep in extras["regression"]}
    assert "pymupdf" in regression_deps


def test_active_base_imports_do_not_pull_optional_provider_boundaries() -> None:
    violations: dict[str, list[str]] = {}
    for path in ACTIVE_BASE_FILES:
        forbidden = _top_imports(path) & FORBIDDEN_ACTIVE_IMPORTS
        if forbidden:
            violations[str(path.relative_to(ROOT))] = sorted(forbidden)

    assert violations == {}
