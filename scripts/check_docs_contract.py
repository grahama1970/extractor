#!/usr/bin/env python3
"""Validate active Extractor documentation against the zero-choice contract."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

import tomllib


ROOT = Path(__file__).resolve().parents[1]

ACTIVE_DOCS = [
    ROOT / "README.md",
    ROOT / "CONTEXT.md",
    ROOT / "docs/STATE_OF_PROJECT.md",
    ROOT / "docs/PROJECT_KNOWLEDGE.md",
    ROOT / "docs/03_guides/HAPPYPATH_GUIDE.md",
    ROOT / "docs/SMOKES_GUIDE.md",
    ROOT / "REVIEW_REQUEST.md",
]

REQUIRED_PATHS = [
    ROOT / "LICENSE",
    ROOT / "pyproject.toml",
    ROOT / "src/extractor/cli_app.py",
    ROOT / "src/extractor/application/extract_file.py",
    ROOT / "src/extractor/core/schema/extraction_result.py",
    ROOT / "src/extractor/core/providers/registry.py",
    ROOT / "src/extractor/core/providers/pdf.py",
    ROOT / "scripts/ci_core.sh",
    ROOT / "scripts/check_docs_contract.py",
    ROOT / "tests/contracts",
    ROOT / "data/input/twins/preset_twin/preset_twin.pdf",
]

QUICK_START_HEADINGS = ("## Normal Quick Start", "## Canonical Entrypoint")
FORBIDDEN_QUICK_COMMAND_TOKENS = (
    "--mode",
    "--preset",
    "--use-llm",
    "--skip-",
    "CHUTES_",
    "SCILLM_",
    "ARANGO_",
)


def fail(message: str) -> None:
    print(f"docs_contract_failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        fail(f"missing required doc: {path.relative_to(ROOT)}")
        raise AssertionError from exc


def markdown_section(text: str, heading: str) -> str:
    start = text.find(heading)
    if start == -1:
        return ""
    next_heading = re.search(r"^## ", text[start + len(heading) :], flags=re.MULTILINE)
    if not next_heading:
        return text[start:]
    end = start + len(heading) + next_heading.start()
    return text[start:end]


def fenced_commands(section: str) -> list[str]:
    commands: list[str] = []
    for match in re.finditer(r"```(?:bash|text)?\n(.*?)```", section, flags=re.DOTALL):
        commands.append(match.group(1))
    return commands


def check_paths_exist() -> None:
    for path in REQUIRED_PATHS:
        if not path.exists():
            fail(f"referenced path does not exist: {path.relative_to(ROOT)}")


def check_license() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    license_value = pyproject["project"]["license"]
    readme = read(ROOT / "README.md")
    license_text = read(ROOT / "LICENSE")
    if license_value != "GPL-3.0-or-later":
        fail(f"unexpected package license metadata: {license_value}")
    if "GNU GENERAL PUBLIC LICENSE" not in license_text:
        fail("LICENSE is not GPL text")
    if "GPL-3.0-or-later" not in readme:
        fail("README license does not match package metadata")


def check_quick_starts() -> None:
    for path in ACTIVE_DOCS:
        text = read(path)
        for heading in QUICK_START_HEADINGS:
            section = markdown_section(text, heading)
            if not section:
                continue
            commands = "\n".join(fenced_commands(section))
            if not commands:
                fail(f"{path.relative_to(ROOT)} {heading} has no fenced command")
            if "uv run extractor extract" not in commands:
                fail(f"{path.relative_to(ROOT)} {heading} does not use canonical extractor")
            for token in FORBIDDEN_QUICK_COMMAND_TOKENS:
                if token in commands:
                    fail(f"{path.relative_to(ROOT)} {heading} exposes forbidden token {token}")


def check_active_docs_contract_language() -> None:
    readme = read(ROOT / "README.md")
    knowledge = read(ROOT / "docs/PROJECT_KNOWLEDGE.md")
    for phrase in [
        "Normal callers provide a supported file",
        "They do not choose PDF",
        "extractor.result.v1",
        "grahama1970/pdf_oxide",
        "grahama1970/tau",
        "agent-skills `extractor`",
    ]:
        if phrase not in readme:
            fail(f"README missing contract phrase: {phrase}")
    for status in ["complete", "degraded", "blocked", "failed"]:
        if f"`{status}`" not in readme:
            fail(f"README missing result status: {status}")
    for phrase in [
        "Current Architecture Decision",
        "Canonical Entrypoint",
        "Internal Boundaries",
        "Explicit Non-Claims",
        "Latest Deterministic Proof Commands",
    ]:
        if phrase not in knowledge:
            fail(f"PROJECT_KNOWLEDGE missing section: {phrase}")


def run_command(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def check_cli_parses() -> None:
    run_command(["uv", "run", "extractor", "--help"])
    run_command(["uv", "run", "extractor", "extract", "--help"])
    with tempfile.TemporaryDirectory(prefix="extractor-docs-contract-") as tmp:
        completed = subprocess.run(
            [
                "uv",
                "run",
                "extractor",
                "extract",
                "data/input/twins/preset_twin/preset_twin.pdf",
                "--out",
                tmp,
                "--offline",
                "--format",
                "json",
            ],
            cwd=ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    if '"schema_version":"extractor.result.v1"' not in completed.stdout.replace(" ", ""):
        fail("canonical docs extraction command did not emit extractor.result.v1 JSON")


def main() -> None:
    check_paths_exist()
    check_license()
    check_quick_starts()
    check_active_docs_contract_language()
    check_cli_parses()
    print("docs_contract_ok")


if __name__ == "__main__":
    main()
