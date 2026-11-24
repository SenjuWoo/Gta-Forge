"""Compile C++ (CMake + MSVC) and C# (dotnet) in a scratch copy. Never builds inside the game."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from .util import ForgeError, find_tool, run


def run(project: Path, game: Path) -> dict:
    if not project.is_dir():
        raise ForgeError(f"no project: {project}", "gtaforge new <name> first")
    scratch = Path(tempfile.mkdtemp(prefix="gtaforge_build_"))
    try:
        dst = scratch / project.name
        shutil.copytree(project, dst, ignore=shutil.ignore_patterns(".git", "build", ".venv", "__pycache__"))
        cmake = find_tool("cmake")
        if (dst / "CMakeLists.txt").is_file():
            if not cmake:
                raise ForgeError("cmake not found", "install CMake (or run from a Developer prompt)")
            cfg = run([cmake, "-S", str(dst), "-B", str(dst / "build"), "-G", "Ninja"], timeout=300)
            if cfg["code"]:
                return {"stage": "configure", **cfg, "evidence": {"compile": "failed"}}
            b = run([cmake, "--build", str(dst / "build")], timeout=600)
            return {"stage": "build", **b, "evidence": {"compile": "passed" if b["code"] == 0 else "failed"}}
        csproj = next(dst.rglob("*.csproj"), None)
        if csproj:
            dotnet = find_tool("dotnet")
            if not dotnet:
                raise ForgeError("dotnet not found", "install .NET SDK")
            b = run([dotnet, "build", str(csproj), "-c", "Release"], timeout=600)
            return {"stage": "build", **b, "evidence": {"compile": "passed" if b["code"] == 0 else "failed"}}
        raise ForgeError("no CMakeLists.txt or .csproj in the project", "use a template: gtaforge new <name> --kind cpp|shvdn")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)