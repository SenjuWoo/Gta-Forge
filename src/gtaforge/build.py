"""Build a native plugin (CMake, see compilemod) or pack an archive (CodeWalker / ragekit)."""
from __future__ import annotations

from pathlib import Path

from .util import ForgeError, find_tool, run


def run(project: Path, game: Path, target: str = "auto") -> dict:
    from .compilemod import run as compile_run
    if target in ("auto", "native"):
        if (project / "CMakeLists.txt").is_file() or list(project.rglob("*.csproj")):
            return compile_run(project, game)
    if target in ("auto", "archive"):
        rk = find_tool("ragekit")
        if rk:
            return {"engine": "ragekit", **run([rk, "pack", str(project)], timeout=600)}
        raise ForgeError("no archive packer (ragekit) and no native project",
                         "build ragekit (vendor/ragekit-main) or add CMakeLists.txt; CodeWalker packs via its GUI")
    raise ForgeError(f"unknown target {target}", "auto | native | archive")