"""Build everything a project produces: native code (compilemod) and archives.

Archives: every folder in the project named `<name>.rpf` (e.g. `dlc.rpf/`) is packed into
`build/<name>.rpf` as an OPEN RPF7 (python writer; `--encryption ng` needs ragekit + keys).
"""
from __future__ import annotations

from pathlib import Path

from . import rpf7
from .util import ForgeError, find_tool, run_proc


def archive_dirs(project: Path) -> list[Path]:
    return sorted(p for p in project.rglob("*.rpf") if p.is_dir() and "build" not in p.relative_to(project).parts)


def pack_archives(project: Path, encryption: str = "open") -> list[dict]:
    out = []
    for d in archive_dirs(project):
        dest = project / "build" / d.relative_to(project)
        if encryption in rpf7.PLAIN:
            out.append(rpf7.pack(d, dest, encryption=encryption))
            continue
        rk = find_tool("ragekit")
        if not rk:
            raise ForgeError(f"{encryption} archives need ragekit", "build ragekit or use --encryption open")
        dest.parent.mkdir(parents=True, exist_ok=True)
        r = run_proc([rk, "rpf", "pack", str(d), str(dest), f"--{encryption}"], timeout=1800)
        if r["code"]:
            raise ForgeError(f"ragekit pack failed: {(r['stderr'] or r['stdout']).strip()[-300:]}", "gtaforge rpf keys first")
        out.append({"archive": str(dest), "encryption": encryption, "bytes": dest.stat().st_size})
    return out


def run(project: Path, game: Path | None = None, target: str = "auto", encryption: str = "open") -> tuple[dict, int]:
    if target not in ("auto", "native", "archive"):
        raise ForgeError(f"unknown target {target}", "auto | native | archive")
    result: dict = {"project": str(project)}
    did = False
    if target in ("auto", "native") and ((project / "CMakeLists.txt").is_file() or list(project.glob("*.csproj"))):
        from .compilemod import run as compile_run
        result["native"] = compile_run(project, game)
        did = True
    if target in ("auto", "archive") and archive_dirs(project):
        result["archives"] = pack_archives(project, encryption)
        did = True
    if not did:
        raise ForgeError("nothing to build", "add CMakeLists.txt / a .csproj, or a <name>.rpf folder to pack")
    ok = result.get("native", {}).get("ok", True)
    result["ok"] = ok
    return result, (0 if ok else 1)
