"""Mod project: manifest (gtaforge.json), templates, find, bump."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .util import ForgeError, TEMPLATES_DIR, load_json, save_json

MANIFEST = "gtaforge.json"


def templates() -> dict[str, str]:
    if not TEMPLATES_DIR.is_dir():
        return {}
    return {p.name: p for p in sorted(TEMPLATES_DIR.iterdir()) if p.is_dir()}


def find_project(explicit: str | None = None) -> Path:
    start = Path(explicit) if explicit else Path.cwd()
    for p in [start, *start.parents]:
        if (p / MANIFEST).is_file():
            return p
    raise ForgeError(f"no {MANIFEST} in {start} or its parents", "start one: gtaforge new <name> --kind cpp")


def create(name: str, folder: str | None = None, kinds: list[str] | None = None, game: str | None = None, force: bool = False) -> dict:
    kinds = kinds or ["cpp"]
    tpls = templates()
    bad = [k for k in kinds if k not in tpls]
    if bad:
        raise ForgeError(f"unknown kind(s): {', '.join(bad)}", "kinds: " + ", ".join(tpls))
    root = Path(folder) if folder else Path.cwd() / name
    game = game or "auto"
    if root.exists() and any(root.iterdir()) and not force:
        raise ForgeError(f"folder not empty: {root}", "pass --force to add kinds into it")
    root.mkdir(parents=True, exist_ok=True)
    import shutil
    for k in kinds:
        for src in (tpls[k]).rglob("*"):
            rel = src.relative_to(tpls[k])
            dst = root / rel
            if src.is_dir():
                dst.mkdir(parents=True, exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                text = src.read_text(encoding="utf-8").replace("{{name}}", name).replace("{{game}}", game)
                dst.write_text(text, encoding="utf-8")
    manifest_path = root / MANIFEST
    if manifest_path.is_file():
        m = load_json(manifest_path)
    else:
        m = {"schema": 1, "name": name, "version": "0.1.0", "game": game or "auto", "kinds": [],
             "entry": {}, "files": [], "dependencies": {}}
    m["kinds"] = sorted(set(m["kinds"]) | set(kinds))
    save_json(manifest_path, m)
    return {"created": str(root), "kinds": m["kinds"], "manifest": str(manifest_path)}


def bump(project: Path, part: str) -> dict:
    m = load_json(project / MANIFEST)
    major, minor, patch = (int(x) for x in m["version"].split(".")[:3])
    if part == "major":
        major, minor, patch = major + 1, 0, 0
    elif part == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    old = m["version"]
    m["version"] = f"{major}.{minor}.{patch}"
    save_json(project / MANIFEST, m)
    for name in ("CHANGELOG.md",):
        p = project / name
        if p.is_file():
            text = p.read_text(encoding="utf-8")
            text = re.sub(r"^## \[?[0-9]+\.[0-9]+\.[0-9]+\]?", f"## {m['version']}", text, count=1, flags=re.M)
            p.write_text(text, encoding="utf-8")
    return {"old": old, "new": m["version"], "manifest": str(project / MANIFEST)}