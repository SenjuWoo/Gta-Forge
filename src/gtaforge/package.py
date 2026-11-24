"""Deterministic runtime zip + receipt. Runtime files only: no tests, logs, STATE, changelogs, backups."""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from pathlib import Path

from .util import ForgeError, load_json, save_json, sha256

EXCLUDE_DIRS = {".git", "tests", "test", ".venv", "__pycache__", "build", "dist", "docs", "artifacts", ".github"}
EXCLUDE_FILES = re.compile(r"(?i)(^|/)(STATE\.md|PLAN\.md|CHANGELOG\.md|WORKSPACE_OWNERSHIP\.md|AGENTS\.md|CLAUDE\.md|gtaforge\.json|.*\.log|.*\.pdb|.*\.zip|.*\.7z)$")
SECRET = re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}")


def runtime_files(project: Path) -> list[Path]:
    out = []
    for p in sorted(project.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(project)
        if any(part in EXCLUDE_DIRS for part in rel.parts) or EXCLUDE_FILES.search(rel.as_posix()):
            continue
        out.append(p)
    return out


def run(project: Path, out: str | None = None) -> dict:
    m = load_json(project / "gtaforge.json")
    files = runtime_files(project)
    if not files:
        raise ForgeError("no runtime files to package", "add the mod payload (scripts/, .asi, data/) to the project")
    dest = Path(out) if out else project / "artifacts" / f"{m['name']}-{m['version']}.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            data = p.read_bytes()
            if SECRET.search(data.decode("utf-8", errors="ignore")):
                raise ForgeError(f"possible secret in {p.relative_to(project)}", "remove it; never ship keys")
            name = p.relative_to(project).as_posix()
            z.writestr(name, data)
            entries.append({"name": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    dest.write_bytes(buf.getvalue())
    receipt = {"name": m["name"], "version": m["version"], "archive": str(dest), "sha256": sha256(dest),
               "files": entries, "gaps": ["load not run", "gameplay not run"]}
    save_json(dest.with_suffix(".receipt.json"), receipt)
    return {"archive": str(dest), "sha256": receipt["sha256"], "files": len(entries), "receipt": str(dest.with_suffix(".receipt.json"))}


def validate(archive: Path) -> tuple[dict, int]:
    if not archive.is_file():
        raise ForgeError(f"no archive: {archive}", "gtaforge package first")
    problems = []
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        for n in names:
            if any(part in EXCLUDE_DIRS for part in n.split("/")) or EXCLUDE_FILES.search(n):
                problems.append({"name": n, "problem": "non-runtime file in package"})
        for n in names:
            try:
                if SECRET.search(z.read(n).decode("utf-8", errors="ignore")):
                    problems.append({"name": n, "problem": "possible secret"})
            except (KeyError, OSError):
                problems.append({"name": n, "problem": "unreadable"})
    return {"archive": str(archive), "sha256": sha256(archive), "files": len(names), "problems": problems,
            "evidence": {"package": "failed" if problems else "passed", "load": "not run", "gameplay": "not run"}}, (1 if problems else 0)