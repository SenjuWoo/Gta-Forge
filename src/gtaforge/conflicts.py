"""Mods fighting over the same files (scripts/, asi, dlcpacks) or anim dicts."""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from pathlib import Path

from .project import load_manifest


def _owners(paths: list[Path]) -> dict[str, list[str]]:
    out = defaultdict(list)
    for p in paths:
        out[p.name].append(str(p))
    return out


def run(project: Path, game: Path) -> dict:
    m = load_manifest(project)
    groups = {
        "asi": list(game.glob("*.asi")),
        "scripts": list((game / "scripts").rglob("*")) if (game / "scripts").is_dir() else [],
        "dlcpacks": [p for p in (game / "update/x64/dlcpacks").glob("*/") ] if (game / "update/x64/dlcpacks").is_dir() else [],
    }
    dupes = {k: {n: v for n, v in _owners(v).items() if len(v) > 1} for k, v in groups.items()}
    dupes = {k: v for k, v in dupes.items() if v}
    own = [p for p in project.rglob("*") if p.is_file() and p.suffix.lower() in (".asi", ".dll", ".cs", ".lua")]
    clashes = []
    for p in own:
        for q in groups["scripts"]:
            if q.is_file() and q.name == p.name and q.stat().st_size == p.stat().st_size:
                clashes.append({"project": str(p), "game": str(q)})
    return {"project": m["name"], "duplicate_names": dupes, "identical_to_game": clashes,
            "note": "same name in two script mods is a conflict risk; identical bytes mean the forge already deployed it"}