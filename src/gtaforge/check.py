"""Project validation: manifest, static script checks, Menyoo hashes, payload, optional compile, optional game.

Errors fail the check (exit 1); warnings are reported; gaps say which evidence tiers did not run.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .package import NON_RUNTIME, resolve_payload
from .project import load_manifest
from .scripts import check_folder, detect
from .util import ForgeError, joaat


def check_spooner(f: Path, errors: list, warnings: list) -> int:
    try:
        root = ET.parse(f).getroot()
    except ET.ParseError as e:
        errors.append({"file": str(f), "problem": f"XML: {e}"})
        return 0
    if root.tag != "SpoonerPlacements":
        return 0
    n = 0
    for pl in root.iter("Placement"):
        n += 1
        mh = (pl.findtext("ModelHash") or "").strip()
        name = (pl.findtext("HashName") or "").strip()
        if not mh:
            errors.append({"file": str(f), "placement": n, "problem": "Placement without ModelHash"})
            continue
        try:
            val = int(mh, 16) if mh.lower().startswith("0x") else int(mh) & 0xFFFFFFFF
        except ValueError:
            errors.append({"file": str(f), "placement": n, "problem": f"ModelHash '{mh}' is not a number"})
            continue
        if name and re.fullmatch(r"[A-Za-z0-9_]+", name) and int(joaat(name), 16) != val:
            warnings.append({"file": str(f), "placement": n, "model": name,
                             "problem": f"ModelHash {mh} != joaat('{name}') 0x{joaat(name)} (HashName may be a display name)"})
        if (pl.findtext("Type") or "").strip() not in ("1", "2", "3"):
            errors.append({"file": str(f), "placement": n, "problem": "Type must be 1 (ped), 2 (vehicle) or 3 (object)"})
    return n


def run(project: Path, compile_: bool = False, game: Path | None = None) -> tuple[dict, int]:
    m = load_manifest(project)
    errors, warnings, gaps = [], [], []
    for key in ("name", "version", "kinds"):
        if not m.get(key):
            errors.append({"problem": f"manifest missing {key}"})
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(m.get("version", ""))):
        errors.append({"problem": f"version '{m.get('version')}' is not MAJOR.MINOR.PATCH"})
    kinds = detect(project)
    missing = [k for k in m.get("kinds", []) if k not in kinds and k != "menyoo"]
    if missing:
        warnings.append({"problem": f"manifest kinds not detected in the folder: {missing}", "detected": kinds})
    static = check_folder(project)
    errors += static["errors"]
    warnings += static["warnings"]
    placements = sum(check_spooner(f, errors, warnings) for f in project.rglob("*.xml")
                     if "build" not in f.relative_to(project).parts)
    for f in project.rglob("*"):
        rel = f.relative_to(project)
        if f.is_file() and f.suffix.lower() in (".asi", ".dll", ".exe") and rel.parts[0] not in ("build", "bin", "obj", "artifacts"):
            warnings.append({"file": rel.as_posix(), "problem": "binary outside build/ or bin/: build it, do not commit it"})
    if game is not None:
        if m.get("game") in (None, "auto"):
            warnings.append({"problem": "manifest game is auto; set legacy | enhanced | both"})
        from .game import edition
        ed = edition(game).get("edition")
        if m.get("game") in ("legacy", "enhanced") and ed and ed != m["game"]:
            errors.append({"problem": f"project targets {m['game']}, installed game is {ed}"})
    comp = None
    if compile_:
        from .compilemod import run as crun
        try:
            comp = crun(project, game)
        except ForgeError as e:
            errors.append({"problem": f"compile could not run: {e}", "fix": e.fix})
        else:
            for r in comp["results"]:
                if r["evidence"]["compile"] != "passed":
                    errors.append({"problem": f"{r['kind']} compile failed at {r['stage']}", "log": r.get("log", "")[-1500:]})
    else:
        gaps.append("compile not run: gtaforge check --compile")
    payload = resolve_payload(project, m)
    for src, dest in payload:
        if NON_RUNTIME.search(dest):
            errors.append({"file": dest, "problem": "payload ships a source/notes file"})
    if m.get("payload") and not payload:
        (warnings if not compile_ else errors).append({"problem": "payload rules match no files yet", "rules": m["payload"],
                                                       "fix": "gtaforge compile, or fix the globs"})
    gaps += ["load not run: gtaforge deploy, launch story mode with -nobattleye, gtaforge logs", "gameplay not run"]
    code = 1 if errors else 0
    return {"project": str(project), "name": m["name"], "version": m.get("version"), "kinds": kinds,
            "native_calls": static["native_calls"], "spooner_placements": placements,
            "payload": [{"from": s.relative_to(project).as_posix(), "to": d} for s, d in payload],
            "compile": comp, "errors": errors, "warnings": warnings, "gaps": gaps,
            "evidence": {"static": "failed" if any("compile" not in e.get("problem", "") for e in errors) else "passed",
                         "compile": (comp["evidence"]["compile"] if comp else "not run"), "load": "not run", "gameplay": "not run"}}, code
