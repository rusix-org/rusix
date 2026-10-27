# SPDX-License-Identifier: GPL-2.0-only
"""Repository paths shared by the Python entry points.

Keep this contract aligned with repo-paths.sh. Overrides are paths, never shell
expressions, and relative overrides are interpreted from the caller's directory.
"""
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class RepoPaths:
    source: Path
    project: Path
    output: Path
    tools: Path


def resolve_paths() -> RepoPaths:
    source = Path(__file__).resolve().parents[2]
    try:
        git_root = subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "--show-toplevel"],
            text=True, stderr=subprocess.PIPE,
        ).strip()
    except subprocess.CalledProcessError as exc:
        raise SystemExit("rusix scripts require a Git checkout") from exc
    if Path(git_root).resolve() != source:
        raise SystemExit("rusix scripts must live in the Git root at rusix/scripts.")
    output = Path(os.environ.get("RUSIX_OUTPUT_ROOT") or f"{source}-out").resolve()
    tools = Path(os.environ.get("RUSIX_TOOLS_ROOT") or output / ".tools/root").resolve()
    return RepoPaths(source, source / "rusix", output, tools)
