"""Project validation against the manifest and the installed game. Errors / warnings / gaps / checked."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .scripts import detect
from .util import ForgeError, load_json


def run(project: Path, compile_: bool = False, game: Path | None = None) -> tuple[dict, int]:
    if not (project / "gtaforge.json").is_file():
        raise ForgeError(f"no gtaforge.json in {project}", "gtaforge new <name> first")
    m = load_json(project / "gtaforge.json")
    errors, warnings, gaps = [], [], []
    for key in ("name", "version", "kinds"):
        if not m.get(key):
            errors.append({"problem": f"manifest missing {key}"})
    kinds = detect(project)
    missing = [k for k in m.get("kinds", []) if k not in kinds]
    if missing:
        warnings.append({"problem": f"manifest kinds not detected: {missing}", "detected": kinds})
    for f in project.rglob("*"):
        if f.is_file() and f.suffix.lower() in (".asi", ".dll", ".exe", ".pdb", ".zip", ".7z"):
            warnings.append({"file": str(f.relative_to(project)), "problem": "binary in source tree; build to build/ and package from there"})
    if game is not None:
        if not m.get("game") or m["game"] == "auto":
            warnings.append({"problem": "manifest game is auto; set legacy|enhanced|both"})
        if "lua" in kinds and not (game / "scripts").is_dir():
            gaps.append("game has no scripts/ folder yet (deploy creates it)")
    if compile_:
        from .compilemod import run as crun
        r = crun(project, game or project)
        if r.get("code"):
            errors.append({"problem": "compile failed", "detail": r.get("stderr", "")[-500:]})
    else:
        gaps.append("compile not run: gtaforge check --compile (or gtaforge compile)")
    gaps += ["load not run: gtaforge deploy then launch with -nobattleye", "gameplay not run"]
    code = 1 if (errors or warnings) else 0
    return {"project": str(project), "version": m.get("version"), "errors": errors, "warnings": warnings,
            "gaps": gaps, "checked": len(list(project.rglob("*"))),
            "evidence": {"static": "failed" if errors else "passed", "compile": "passed" if compile_ and not any("compile" in e["problem"] for e in errors) else "not run"}}, code