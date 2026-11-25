"""Mod project: manifest (gtaforge.json), templates, find, bump.

Manifest schema 2:
  name, version, game (legacy|enhanced|both|auto), kinds,
  payload: [{"from": "<glob relative to the project>", "to": "<folder relative to the game root>"}]
           what package/deploy ship - build outputs and data, never sources.
"""
from __future__ import annotations

import re
from pathlib import Path

from .util import ForgeError, TEMPLATES_DIR, joaat, load_json, save_json

MANIFEST = "gtaforge.json"
NAME_OK = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")

# What each kind ships by default. {{name}} is replaced at creation.
DEFAULT_PAYLOAD = {
    "cpp": [{"from": "build/*.asi", "to": "."}],
    "shvdn": [{"from": "bin/Release/{{name}}.dll", "to": "scripts"}],
    "menyoo": [{"from": "menyooStuff/**/*", "to": "menyooStuff"}],
    "xml": [],
    "lua": [],   # FiveM resource: package zips it; it is never deployed into single-player GTA V
}
GITIGNORE = "build/\nbin/\nobj/\nartifacts/\n*.user\n.vs/\n"


def templates() -> dict[str, Path]:
    if not TEMPLATES_DIR.is_dir():
        return {}
    return {p.name: p for p in sorted(TEMPLATES_DIR.iterdir()) if p.is_dir()}


def find_project(explicit: str | None = None) -> Path:
    start = Path(explicit) if explicit else Path.cwd()
    for p in [start, *start.parents]:
        if (p / MANIFEST).is_file():
            return p
    raise ForgeError(f"no {MANIFEST} in {start} or its parents", "start one: gtaforge new <name> --kind cpp")


def load_manifest(project: Path) -> dict:
    p = project / MANIFEST
    if not p.is_file():
        raise ForgeError(f"no {MANIFEST} in {project}", "gtaforge new <name> first")
    try:
        m = load_json(p)
    except ValueError as e:
        raise ForgeError(f"{MANIFEST} is not valid JSON: {e}", "fix the file") from None
    if not isinstance(m, dict) or not m.get("name") or not m.get("version"):
        raise ForgeError(f"{MANIFEST} needs name and version", "fix the file or recreate with gtaforge new")
    if "payload" not in m:  # schema 1 projects: derive the payload from the kinds
        m["payload"] = [dict(r, **{"from": r["from"].replace("{{name}}", m["name"])})
                        for k in m.get("kinds", []) for r in DEFAULT_PAYLOAD.get(k, [])]
    return m


def _render(text: str, name: str, game: str) -> str:
    text = text.replace("{{name}}", name).replace("{{game}}", game)
    return re.sub(r"\{\{joaat:([^}]+)\}\}", lambda m: "0x" + joaat(m.group(1)), text)


def create(name: str, folder: str | None = None, kinds: list[str] | None = None, game: str | None = None,
           force: bool = False) -> dict:
    if not NAME_OK.match(name):
        raise ForgeError(f"bad project name '{name}'", "letters, digits, _ . - ; start with a letter; max 64")
    kinds = kinds or ["cpp"]
    tpls = templates()
    bad = [k for k in kinds if k not in tpls]
    if bad:
        raise ForgeError(f"unknown kind(s): {', '.join(bad)}", "kinds: " + ", ".join(tpls))
    game = game or "auto"
    if game not in ("auto", "legacy", "enhanced", "both"):
        raise ForgeError(f"bad --game '{game}' for a project", "legacy | enhanced | both | auto")
    root = Path(folder) if folder else Path.cwd() / name
    if root.exists() and any(root.iterdir()) and not force:
        raise ForgeError(f"folder not empty: {root}", "pass --force to add kinds into it")
    root.mkdir(parents=True, exist_ok=True)
    written = []
    for k in kinds:
        for src in sorted(tpls[k].rglob("*")):
            rel = Path(_render(str(src.relative_to(tpls[k])), name, game))
            dst = root / rel
            if src.is_dir():
                dst.mkdir(parents=True, exist_ok=True)
                continue
            if dst.exists() and not force:
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(_render(src.read_text(encoding="utf-8"), name, game), encoding="utf-8", newline="\n")
            written.append(rel.as_posix())
    if "cpp" in kinds and not (root / "inc" / "natives.h").is_file():
        from .natives import header
        header(root / "inc" / "natives.h")
        written.append("inc/natives.h")
    for extra, text in ((".gitignore", GITIGNORE), ("CHANGELOG.md", f"# Changelog\n\n## 0.1.0\n- First version of {name}.\n")):
        if not (root / extra).exists():
            (root / extra).write_text(text, encoding="utf-8", newline="\n")
            written.append(extra)
    manifest_path = root / MANIFEST
    m = load_json(manifest_path) if manifest_path.is_file() else {
        "schema": 2, "name": name, "version": "0.1.0", "game": game, "kinds": [], "payload": [], "dependencies": {}}
    m.setdefault("payload", [])
    m["schema"] = 2
    for k in kinds:
        if k not in m["kinds"]:
            m["kinds"].append(k)
            for r in DEFAULT_PAYLOAD.get(k, []):
                rule = {"from": r["from"].replace("{{name}}", name), "to": r["to"]}
                if rule not in m["payload"]:
                    m["payload"].append(rule)
    if "cpp" in kinds:
        m["dependencies"].setdefault("ScriptHookV", "https://dev-c.com/gtav/scripthookv/")
    if "shvdn" in kinds:
        m["dependencies"].setdefault("ScriptHookVDotNet", "https://github.com/scripthookvdotnet/scripthookvdotnet/releases")
    if "menyoo" in kinds:
        m["dependencies"].setdefault("Menyoo", "https://github.com/itsjustcurtis/MenyooSP/releases")
    save_json(manifest_path, m)
    return {"created": str(root), "kinds": m["kinds"], "manifest": str(manifest_path), "files": written,
            "payload": m["payload"], "next": "gtaforge check --compile --project " + str(root)}


def bump(project: Path, part: str) -> dict:
    m = load_manifest(project)
    try:
        major, minor, patch = (int(x) for x in str(m["version"]).split(".")[:3])
    except ValueError:
        raise ForgeError(f"version '{m['version']}' is not MAJOR.MINOR.PATCH", "fix gtaforge.json") from None
    if part == "major":
        major, minor, patch = major + 1, 0, 0
    elif part == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    old = m["version"]
    m["version"] = f"{major}.{minor}.{patch}"
    raw = load_json(project / MANIFEST)
    raw["version"] = m["version"]
    save_json(project / MANIFEST, raw)
    touched = [MANIFEST]
    ch = project / "CHANGELOG.md"
    if ch.is_file():
        text = ch.read_text(encoding="utf-8")
        if f"## {m['version']}" not in text:
            text = re.sub(r"^(# [^\n]*\n+)", rf"\1## {m['version']}\n- \n\n", text, count=1) if text.startswith("# ") \
                else f"## {m['version']}\n- \n\n" + text
            ch.write_text(text, encoding="utf-8", newline="\n")
            touched.append("CHANGELOG.md")
    for csproj in project.glob("*.csproj"):
        t = csproj.read_text(encoding="utf-8")
        t2 = re.sub(r"<Version>[^<]*</Version>", f"<Version>{m['version']}</Version>", t)
        if t2 != t:
            csproj.write_text(t2, encoding="utf-8", newline="\n")
            touched.append(csproj.name)
    return {"old": old, "new": m["version"], "touched": touched}
