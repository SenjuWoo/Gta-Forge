"""Payload resolution, deterministic runtime zip + receipt, and zip validation.

The manifest's payload rules decide what ships: each {"from": glob, "to": folder} maps project
files (build outputs, data) to a folder relative to the game root. The zip mirrors the game layout,
so "unzip into the game folder" is the install.
"""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from pathlib import Path, PurePosixPath

from .project import load_manifest
from .util import ForgeError, save_json, sha256

NON_RUNTIME = re.compile(r"(?i)(^|/)(STATE\.md|PLAN\.md|CHANGELOG\.md|WORKSPACE_OWNERSHIP\.md|AGENTS\.md|CLAUDE\.md|"
                         r"DECISIONS\.md|VALIDATION\.md|gtaforge\.json|.*\.log|.*\.pdb|.*\.ilk|.*\.exp|.*\.lib|.*\.obj|"
                         r".*\.cpp|.*\.h|.*\.hpp|.*\.cs|.*\.csproj|.*\.sln|CMakeLists\.txt|CMakeCache\.txt|.*\.zip|.*\.7z)$")
NON_RUNTIME_DIRS = {".git", "tests", "test", ".venv", "__pycache__", "obj", ".github", ".vs", "cmakefiles"}
SECRET = re.compile(r"(?i)(api[_-]?key|secret|token|password|bearer)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}")
ZIP_TIME = (2020, 1, 1, 0, 0, 0)  # fixed timestamps -> byte-identical zips for identical inputs


def _safe_rel(to: str) -> PurePosixPath:
    rel = PurePosixPath(to.replace("\\", "/"))
    if rel.is_absolute() or ".." in rel.parts or (rel.parts and ":" in rel.parts[0]):
        raise ForgeError(f"payload target escapes the game folder: '{to}'", "use a folder relative to the game root")
    return rel


def resolve_payload(project: Path, m: dict | None = None) -> list[tuple[Path, str]]:
    """[(source file, destination path relative to the game root)] from the manifest's payload rules."""
    m = m or load_manifest(project)
    out: dict[str, Path] = {}
    for rule in m.get("payload", []):
        if not isinstance(rule, dict) or "from" not in rule:
            raise ForgeError(f"bad payload rule: {rule}", 'each rule is {"from": "<glob>", "to": "<game folder>"}')
        dest_root = _safe_rel(rule.get("to", "."))
        pattern = rule["from"].replace("\\", "/").lstrip("/")
        if ".." in PurePosixPath(pattern).parts:
            raise ForgeError(f"payload source escapes the project: '{pattern}'", "use a glob inside the project")
        parts = PurePosixPath(pattern).parts
        # literal folder prefix before the first wildcard part: what sits below it keeps its layout
        lit = []
        for p in parts[:-1]:
            if any(c in p for c in "*?["):
                break
            lit.append(p)
        base = project.joinpath(*lit)
        for src in sorted(project.glob(pattern)):
            if not src.is_file():
                continue
            below = PurePosixPath(src.relative_to(base).as_posix()) if any(c in pattern for c in "*?[") else PurePosixPath(src.name)
            out[str(dest_root / below)] = src
    return sorted(((src, dest) for dest, src in out.items()), key=lambda x: x[1])


def run(project: Path, out: str | None = None) -> dict:
    m = load_manifest(project)
    files = resolve_payload(project, m)
    if not files:
        rules = m.get("payload") or "none"
        raise ForgeError(f"payload is empty (rules: {rules})",
                         "build first (gtaforge compile) or add payload rules to gtaforge.json")
    dest = Path(out) if out else project / "artifacts" / f"{m['name']}-{m['version']}.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for src, name in files:
            data = src.read_bytes()
            if SECRET.search(data.decode("utf-8", errors="ignore")):
                raise ForgeError(f"possible secret in {src.relative_to(project)}", "remove it; never ship keys")
            info = zipfile.ZipInfo(name, ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)
            entries.append({"name": name, "from": src.relative_to(project).as_posix(), "bytes": len(data),
                            "sha256": hashlib.sha256(data).hexdigest()})
    tmp = dest.with_name(dest.name + ".gtaforge_tmp")
    tmp.write_bytes(buf.getvalue())
    tmp.replace(dest)
    receipt = {"name": m["name"], "version": m["version"], "game": m.get("game"), "archive": str(dest),
               "sha256": sha256(dest), "files": entries, "install": "extract into the game folder",
               "evidence": {"package": "built", "load": "not run", "gameplay": "not run"}}
    save_json(dest.with_suffix(".receipt.json"), receipt)
    return {"archive": str(dest), "sha256": receipt["sha256"], "files": len(entries),
            "names": [e["name"] for e in entries], "receipt": str(dest.with_suffix(".receipt.json"))}


def validate(archive: Path) -> tuple[dict, int]:
    if not archive.is_file():
        raise ForgeError(f"no archive: {archive}", "gtaforge package first")
    problems = []
    try:
        z = zipfile.ZipFile(archive)
    except zipfile.BadZipFile:
        raise ForgeError(f"not a zip: {archive}", "pass the zip gtaforge package wrote") from None
    with z:
        names = z.namelist()
        for n in names:
            parts = PurePosixPath(n).parts
            if n.startswith("/") or ".." in parts or (parts and ":" in parts[0]):
                problems.append({"name": n, "problem": "path escapes the install folder"})
            if any(p.lower() in NON_RUNTIME_DIRS for p in parts[:-1]) or NON_RUNTIME.search(n):
                problems.append({"name": n, "problem": "non-runtime file in package (source, notes or build junk)"})
            if n.lower().endswith((".asi", ".dll")) and n.count("/") == 0 and n.lower() in (
                    "scripthookv.dll", "dinput8.dll", "xinput1_4.dll", "scripthookvdotnet.asi", "scripthookvdotnet3.dll"):
                problems.append({"name": n, "problem": "ships a framework file; link the framework instead (no redistribution)"})
            try:
                if SECRET.search(z.read(n).decode("utf-8", errors="ignore")):
                    problems.append({"name": n, "problem": "possible secret"})
            except (KeyError, OSError, zipfile.BadZipFile, RuntimeError):
                problems.append({"name": n, "problem": "unreadable"})
        empty = not [n for n in names if not n.endswith("/")]
        if empty:
            problems.append({"problem": "zip is empty"})
    return {"archive": str(archive), "sha256": sha256(archive), "files": len(names), "problems": problems,
            "evidence": {"package": "failed" if problems else "passed", "load": "not run", "gameplay": "not run"}}, (1 if problems else 0)
