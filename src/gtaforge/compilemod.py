"""Compile C++ (CMake + MSVC, Ninja) and C# (dotnet) in <project>/build and bin/. Never builds inside the game.

MSVC: when cl is not on PATH the environment of vcvars64.bat (found with vswhere) is captured once
and passed to cmake, so a plain shell works.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from .util import ForgeError, find_tool, msvc_env, msvc_install, run_proc


def _tail(text: str, n: int = 40) -> str:
    return "\n".join((text or "").strip().splitlines()[-n:])


def compile_cpp(project: Path) -> dict:
    cmake = find_tool("cmake")
    if not cmake:
        raise ForgeError("cmake not found", "install CMake (winget install Kitware.CMake)")
    sdk = find_tool("shv_sdk")
    if not sdk:
        raise ForgeError("ScriptHookV SDK not found", "set SHV_SDK to the SDK folder (inc/, lib/) or put it in a forge tools dir")
    env = msvc_env()
    if env is None and not shutil.which("cl"):
        inst = msvc_install()
        raise ForgeError("no MSVC C++ toolset", "install Visual Studio Build Tools with 'Desktop development with C++'"
                         + (f" (found {inst['path']} without vcvars64)" if inst else ""))
    build = project / "build"
    gen = ["-G", "Ninja"] if (shutil.which("ninja", path=(env or {}).get("Path") or (env or {}).get("PATH")) or find_tool("ninja")) else []
    cfg = run_proc([cmake, "-S", str(project), "-B", str(build), *gen, "-DCMAKE_BUILD_TYPE=Release", f"-DSHV_SDK={sdk}"],
                   timeout=600, env=env, replace_env=bool(env))
    if cfg["timed_out"] or cfg["code"]:
        return {"stage": "configure", "code": cfg["code"], "log": _tail(cfg["stdout"] + "\n" + cfg["stderr"]),
                "evidence": {"compile": "failed"}}
    b = run_proc([cmake, "--build", str(build), "--config", "Release"], timeout=1200, env=env, replace_env=bool(env))
    outputs = sorted(str(p.relative_to(project)) for p in build.rglob("*.asi"))
    ok = b["code"] == 0 and bool(outputs)
    return {"stage": "build", "code": b["code"], "sdk": sdk, "generator": gen[1] if gen else "default",
            "outputs": outputs, "log": _tail(b["stdout"] + "\n" + b["stderr"], 25 if ok else 60),
            "evidence": {"compile": "passed" if ok else "failed"}}


def compile_cs(project: Path, csproj: Path, game: Path | None) -> dict:
    dotnet = find_tool("dotnet")
    if not dotnet:
        raise ForgeError("dotnet not found", "install the .NET SDK (winget install Microsoft.DotNet.SDK.9)")
    ref = None
    for cand in ([game / "ScriptHookVDotNet3.dll"] if game else []):
        if cand.is_file():
            ref = cand
    ref = ref or (Path(find_tool("shvdn_ref")) if find_tool("shvdn_ref") else None)
    if not ref:
        raise ForgeError("ScriptHookVDotNet3.dll not found", "install SHVDN in the game, or set SHVDN_REF to the dll")
    b = run_proc([dotnet, "build", str(csproj), "-c", "Release", "-nologo", f"-p:SHVDN_REF={ref.parent}",
                  "-p:OutputPath=" + str(project / "bin" / "Release") + "\\"], timeout=1200)
    outputs = sorted(str(p.relative_to(project)) for p in (project / "bin" / "Release").glob("*.dll")
                     if p.name.lower() != "scripthookvdotnet3.dll") if (project / "bin" / "Release").is_dir() else []
    ok = b["code"] == 0 and bool(outputs)
    return {"stage": "build", "code": b["code"], "shvdn_ref": str(ref), "outputs": outputs,
            "log": _tail(b["stdout"] + "\n" + b["stderr"], 25 if ok else 60), "evidence": {"compile": "passed" if ok else "failed"}}


def run(project: Path, game: Path | None = None) -> dict:
    if not project.is_dir():
        raise ForgeError(f"no project: {project}", "gtaforge new <name> first")
    results = []
    if (project / "CMakeLists.txt").is_file():
        results.append({"kind": "cpp", **compile_cpp(project)})
    for csproj in sorted(project.glob("*.csproj")):
        results.append({"kind": "shvdn", **compile_cs(project, csproj, game)})
    if not results:
        raise ForgeError("nothing to compile (no CMakeLists.txt or .csproj at the project root)",
                         "use a template: gtaforge new <name> --kind cpp|shvdn")
    ok = all(r["evidence"]["compile"] == "passed" for r in results)
    return {"project": str(project), "results": results, "ok": ok,
            "evidence": {"compile": "passed" if ok else "failed", "load": "not run", "gameplay": "not run"}}
