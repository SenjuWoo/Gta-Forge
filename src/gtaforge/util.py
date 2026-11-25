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


_VERSION_CACHE: dict[tuple, str | None] = {}
_FIXED_SIG = b"\xbd\x04\xef\xfe"  # VS_FIXEDFILEINFO.dwSignature 0xFEEF04BD


def file_version(path: Path) -> str | None:
    """PE file version from the VS_FIXEDFILEINFO block, read in Python (any OS, no PowerShell).

    Cached per (path, size, mtime): 1.0.0 spawned PowerShell on every call, which made batch
    lookups crawl. None when the file has no version resource."""
    path = Path(path)
    try:
        st = path.stat()
    except OSError:
        return None
    if not path.is_file():
        return None
    key = (str(path).lower(), st.st_size, st.st_mtime_ns)
    if key in _VERSION_CACHE:
        return _VERSION_CACHE[key]
    import mmap
    ver = None
    try:
        with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
            if m[:2] == b"MZ":
                at = m.rfind(_FIXED_SIG)  # the version resource sits in .rsrc near the end
                while at >= 0 and ver is None:
                    sig, strucv, ms, ls = struct.unpack_from("<IIII", m, at)
                    if strucv in (0x00010000, 0):
                        ver = f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
                    else:
                        at = m.rfind(_FIXED_SIG, 0, at)
    except (OSError, ValueError, struct.error):
        ver = None
    _VERSION_CACHE[key] = ver
    return ver


def run_proc(argv: list[str], cwd: Path | None = None, timeout: int = 600, env: dict | None = None, replace_env: bool = False) -> dict:
    """Run a program with argv (never a shell string). Returns {code, stdout, stderr, timed_out}.

    Named run_proc, not run: several modules define their own run(args) entry point, and a
    shared name shadowed this helper there (0.2.0 bug: every external tool call crashed)."""
    import subprocess
    e = dict(env) if (env and replace_env) else dict(os.environ)
    if env and not replace_env:
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


def config() -> dict:
    """Per-user settings (never in the repo): %LOCALAPPDATA%/GTAForge/config.json, e.g. {"tool_dirs": [...]}."""
    p = home_dir() / "config.json"
    try:
        return load_json(p) if p.is_file() else {}
    except (OSError, ValueError):
        return {}


def _tool_dirs() -> list[Path]:
    dirs = []
    env = os.environ.get("GTA_FORGE_TOOLS")
    if env:
        dirs += [Path(x) for x in env.split(os.pathsep) if x]
    dirs.append(home_dir() / "tools")
    dirs += [Path(expand_env(x)) for x in config().get("tool_dirs", [])]
    return dirs


def _scan(d: Path, names: list[str], depth: int = 4) -> str | None:
    """Breadth-first name scan, bounded depth (a tools folder can hold big extracted trees)."""
    wanted = {n.lower() for n in names}
    level = [d]
    for _ in range(depth):
        nxt = []
        for folder in level:
            try:
                kids = sorted(folder.iterdir())
            except OSError:
                continue
            for k in kids:
                if k.is_file() and k.name.lower() in wanted:
                    return str(k)
                if k.is_dir() and not k.name.startswith(".") and k.name.lower() not in ("target", "node_modules", "__pycache__"):
                    nxt.append(k)
        level = nxt
    return None


def _scan_dir(d: Path, marker: str, patterns: list[str], depth: int = 3) -> str | None:
    level = [d]
    for _ in range(depth):
        nxt = []
        for folder in level:
            if (folder / marker).is_file() and any(folder.match(p) for p in patterns or ["*"]):
                return str(folder)
            try:
                nxt += [k for k in sorted(folder.iterdir()) if k.is_dir()]
            except OSError:
                continue
        level = nxt
    return None


def find_tool(tool_id: str) -> str | None:
    import shutil
    reg = load_json(KNOWLEDGE_DIR / "tools.json")
    for t in reg["tools"]:
        if t["id"] != tool_id:
            continue
        if t.get("env") and os.environ.get(t["env"]):
            p = os.environ[t["env"]]
            if Path(p).exists():
                return p
            hit = shutil.which(p)
            if hit:
                return hit
        for name in t.get("names", []):
            hit = shutil.which(name)
            if hit:
                return hit
        for hint in t.get("paths", []) + config().get("tools", {}).get(tool_id, []):
            expanded = expand_env(hint)
            if "%" not in expanded and Path(expanded).exists():
                return str(Path(expanded))
        for d in _tool_dirs():
            if not d.is_dir():
                continue
            if t.get("dir_marker"):
                hit = _scan_dir(d, t["dir_marker"], t.get("dir_names", []))
            else:
                hit = _scan(d, t.get("names", []))
            if hit:
                return hit
    return None


def tools() -> list[dict]:
    reg = load_json(KNOWLEDGE_DIR / "tools.json")
    return [{"id": t["id"], "name": t["name"], "path": find_tool(t["id"]), "role": t["role"],
             "source": t.get("source"), "license": t.get("license")} for t in reg["tools"]]


def read_text(path: Path, limit: int = 2_000_000) -> str:
    data = path.read_bytes()[:limit]
    return data.decode("utf-8", errors="replace")



def joaat(text: str) -> str:
    """Jenkins one-at-a-time over the lowercased UTF-8 text: RAGE names, models, natives' archive hashes.
    Reference: joaat("adder") == "b779a091" (the Adder model hash)."""
    h = 0
    for b in text.lower().encode("utf-8"):
        h = (h + b) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    h = (h + (h << 15)) & 0xFFFFFFFF
    return f"{h:08x}"

def joaat_int(text: str) -> int:
    return int(joaat(text), 16)


def vswhere() -> Path | None:
    base = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    return base if base.is_file() else None


def msvc_install() -> dict | None:
    """Newest Visual Studio / Build Tools with the x64 C++ toolset (vswhere), or None."""
    vw = vswhere()
    if not vw:
        return None
    r = run_proc([str(vw), "-latest", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                  "-format", "json", "-utf8"], timeout=60)
    try:
        items = json.loads(r["stdout"] or "[]")
    except ValueError:
        return None
    if not items:
        return None
    path = Path(items[0]["installationPath"])
    vcvars = path / "VC" / "Auxiliary" / "Build" / "vcvars64.bat"
    return {"path": str(path), "version": items[0].get("installationVersion"), "vcvars64": str(vcvars) if vcvars.is_file() else None}


_MSVC_ENV: dict | None = None


def msvc_env() -> dict | None:
    """The environment vcvars64.bat produces (cl, link, INCLUDE, LIB), captured once per process.
    None when cl is already on PATH (use os.environ) or no Visual Studio C++ toolset exists."""
    global _MSVC_ENV
    import shutil
    if shutil.which("cl"):
        return None
    if _MSVC_ENV is not None:
        return _MSVC_ENV
    inst = msvc_install()
    if not inst or not inst["vcvars64"]:
        return None
    import subprocess
    # cmd parses its own quoting: pass one string (a list would get backslash-escaped quotes).
    try:
        out = subprocess.run(f'cmd /d /s /c ""{inst["vcvars64"]}" >nul 2>&1 && set"', capture_output=True,
                             text=True, errors="replace", timeout=120).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    env = {}
    for line in out.splitlines():
        k, sep, v = line.partition("=")
        if sep and k:
            env[k] = v
    _MSVC_ENV = env if any(k.upper() == "VCTOOLSINSTALLDIR" for k in env) else {}
    return _MSVC_ENV or None
