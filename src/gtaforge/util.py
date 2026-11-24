"""Small shared helpers: hashing, paths, file versions, JSON output."""
from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import sys
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = PKG_DIR / "knowledge"
TEMPLATES_DIR = PKG_DIR / "templates"
BS = "\\"


class ForgeError(Exception):
    """An expected failure with a named cause and a fix. Exit code 2."""

    def __init__(self, message: str, fix: str = "", code: int = 2):
        super().__init__(message)
        self.fix = fix
        self.code = code


def home_dir() -> Path:
    """Where the forge keeps caches and indexes. Never inside the game folder."""
    env = os.environ.get("GTA_FORGE_HOME")
    if env:
        return Path(env)
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "GTAForge"
    return Path.home() / ".cache" / "gta-forge"


def emit(value) -> None:
    text = json.dumps(value, indent=2, ensure_ascii=False, default=str)
    try:
        sys.stdout.write(text + "\n")
    except UnicodeEncodeError:
        sys.stdout.write(json.dumps(value, indent=2, ensure_ascii=True, default=str) + "\n")


def load_json(path: Path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_file(path: Path) -> dict:
    if not path.is_file():
        raise ForgeError(f"no file: {path}", "pass an existing file")
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def file_version(path: Path) -> str | None:
    """PE file version (Windows only, via PowerShell). None elsewhere or on failure."""
    if os.name != "nt" or not path.is_file():
        return None
    import subprocess
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            f"(Get-Item -LiteralPath '{str(path).replace(chr(39), chr(39)*2)}').VersionInfo.FileVersion"],
                           capture_output=True, text=True, timeout=30)
        v = r.stdout.strip()
        return v or None
    except (OSError, subprocess.SubprocessError):
        return None


def run(argv: list[str], cwd: Path | None = None, timeout: int = 600, env: dict | None = None) -> dict:
    """Run a program with argv (never a shell string). Returns {code, stdout, stderr, timed_out}."""
    import subprocess
    e = dict(os.environ)
    if env:
        e.update(env)
    try:
        r = subprocess.run(argv, cwd=str(cwd) if cwd else None, capture_output=True, text=True,
                           errors="replace", timeout=timeout, env=e)
        return {"code": r.returncode, "stdout": r.stdout, "stderr": r.stderr, "timed_out": False}
    except subprocess.TimeoutExpired:
        return {"code": None, "stdout": "", "stderr": "", "timed_out": True}
    except OSError as e:
        raise ForgeError(f"cannot run {argv[0]}: {e}", "install it or set its env var (see gtaforge doctor)")


def expand_env(path: str) -> str:
    return re.sub(r"%(\w+)%", lambda m: os.environ.get(m.group(1), m.group(0)), path)


def _tool_dirs() -> list[Path]:
    dirs = []
    env = os.environ.get("GTA_FORGE_TOOLS")
    if env:
        dirs.append(Path(env))
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        dirs.append(Path(os.environ["LOCALAPPDATA"]) / "GTAForge" / "tools")
    return dirs


def find_tool(tool_id: str) -> str | None:
    import shutil
    reg = load_json(KNOWLEDGE_DIR / "tools.json")
    for t in reg["tools"]:
        if t["id"] != tool_id:
            continue
        if t.get("env") and os.environ.get(t["env"]):
            p = os.environ[t["env"]]
            if Path(p).is_file():
                return p
            hit = shutil.which(p)
            if hit:
                return hit
        for name in t["names"]:
            hit = shutil.which(name)
            if hit:
                return hit
        for hint in t.get("paths", []):
            expanded = expand_env(hint)
            if "%" not in expanded and Path(expanded).is_file():
                return str(Path(expanded))
        for d in _tool_dirs():
            if not d.is_dir():
                continue
            for name in t["names"]:
                hits = sorted(d.rglob(name))
                if hits:
                    return str(hits[0])
    return None


def tools() -> list[dict]:
    reg = load_json(KNOWLEDGE_DIR / "tools.json")
    return [{"id": t["id"], "name": t["name"], "path": find_tool(t["id"]), "role": t["role"],
             "source": t.get("source"), "license": t.get("license")} for t in reg["tools"]]


def read_text(path: Path, limit: int = 2_000_000) -> str:
    data = path.read_bytes()[:limit]
    return data.decode("utf-8", errors="replace")


def tweakdb_id(text: str) -> str:
    """FNV-1a 64 of the lowercased text (GTA V hash convention for labels/ids)."""
    h = 0xCBF29CE484222325
    for b in text.lower().encode("utf-8"):
        h = ((h ^ b) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}"


def joaat(text: str) -> str:
    h = 0
    for b in text.lower().encode("utf-8"):
        h = (h + b) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    h = (h + (h << 15)) & 0xFFFFFFFF
    return f"{h:08x}"