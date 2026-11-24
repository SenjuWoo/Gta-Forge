"""Find the installed GTA V (Legacy / Enhanced / Steam / Epic / Rockstar) and read what is installed. Read-only."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .util import ForgeError, file_version, load_json, KNOWLEDGE_DIR

# (exe names, edition) - first match wins; Enhanced checked first when both exist.
EDITIONS = [
    ("enhanced", ["GTA5_Enhanced.exe"], "update", "x64a.rpf"),
    ("legacy", ["GTA5.exe"], "update", "update.rpf"),
]


def is_game_root(path: Path) -> bool:
    return any((path / exe).is_file() for _ed, exes, _u, _r in EDITIONS for exe in exes)


def _steam_libraries() -> list[Path]:
    roots: list[Path] = []
    steam = None
    if os.name == "nt":
        try:
            import winreg
            for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                              (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
                try:
                    with winreg.OpenKey(hive, key) as k:
                        for name in ("SteamPath", "InstallPath"):
                            try:
                                steam = Path(winreg.QueryValueEx(k, name)[0])
                                break
                            except OSError:
                                continue
                except OSError:
                    continue
                if steam:
                    break
        except ImportError:
            pass
    else:
        for cand in (Path.home() / ".steam/steam", Path.home() / ".local/share/Steam"):
            if cand.is_dir():
                steam = cand
                break
    if steam:
        roots.append(steam)
        vdf = steam / "steamapps" / "libraryfolders.vdf"
        if vdf.is_file():
            for m in re.finditer(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="replace")):
                roots.append(Path(m.group(1).replace("\\\\", "\\")))
    return roots


def _epic_paths() -> list[Path]:
    out: list[Path] = []
    base = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Epic/EpicGamesLauncher/Data/Manifests"
    for item in (sorted(base.glob("*.item")) if base.is_dir() else []):
        try:
            data = json.loads(item.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if "grand theft auto v" in str(data.get("DisplayName", "")).lower() and data.get("InstallLocation"):
            out.append(Path(data["InstallLocation"]))
    return out


def _rockstar_paths() -> list[Path]:
    if os.name != "nt":
        return []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Rockstar Games\Grand Theft Auto V") as k:
            return [Path(winreg.QueryValueEx(k, "installFolder")[0])]
    except (ImportError, OSError):
        return []


def candidates() -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    for env in ("GTA5_ROOT", "GTA_ROOT"):
        if os.environ.get(env):
            out.append((f"env:{env}", Path(os.environ[env])))
    for lib in _steam_libraries():
        out.append(("steam", lib / "steamapps" / "common" / "Grand Theft Auto V Enhanced"))
        out.append(("steam", lib / "steamapps" / "common" / "Grand Theft Auto V"))
    for p in _rockstar_paths():
        out.append(("rockstar", p))
    for p in _epic_paths():
        out.append(("epic", p))
    return out


def find_game(explicit: str | None = None) -> tuple[Path | None, str, list[str]]:
    checked: list[str] = []
    if explicit:
        p = Path(explicit)
        if is_game_root(p):
            return p, "argument", [str(p)]
        raise ForgeError(f"not a GTA V folder (no GTA5_Enhanced.exe / GTA5.exe): {p}",
                         "pass the folder that contains the game exe")
    seen = set()
    for how, p in candidates():
        key = str(p).lower()
        if key in seen:
            continue
        seen.add(key)
        checked.append(str(p))
        if is_game_root(p):
            return p, how, checked
    return None, "", checked


def require_game(explicit: str | None) -> Path:
    root, _, checked = find_game(explicit)
    if root is None:
        raise ForgeError("GTA V install not found",
                         "pass --game <folder> or set GTA5_ROOT; checked: " + ("; ".join(checked) or "nothing"))
    return root


def edition(root: Path) -> dict:
    for ed, exes, upd, rpf in EDITIONS:
        for exe in exes:
            if (root / exe).is_file():
                return {"edition": ed, "exe": exe, "file_version": file_version(root / exe),
                        "update_folder": str(root / upd), "main_rpf": str(root / rpf)}
    return {"edition": None}


def game_version(root: Path) -> dict:
    ed = edition(root)
    facts = load_json(KNOWLEDGE_DIR / "facts.json")["facts"]
    fv = ed.get("file_version")
    known = facts["game.versions"]["value"]
    return {**ed, "patch": known.get(fv) if fv else None,
            "shv_supported": (facts["game.shv_supported"]["value"] if fv else None),
            "note": None if not fv or fv in known else "file version not in the forge's table; update knowledge/facts.json"}


def frameworks(root: Path) -> list[dict]:
    reg = load_json(KNOWLEDGE_DIR / "frameworks.json")
    out = []
    for fw in reg["frameworks"]:
        present = all((root / m).exists() for m in fw["markers"])
        ver = None
        if present and fw.get("version_from"):
            ver = file_version(root / fw["version_from"])
        out.append({"id": fw["id"], "name": fw["name"], "installed": present, "version": ver,
                    "role": fw["role"], "repo": fw.get("repo"), "nexus": fw.get("nexus"),
                    "edition": fw.get("edition", "both")})
    return out


def _count(path: Path, pattern: str) -> int:
    """Entries of one folder matching pattern; a trailing '/' counts folders only (Path.glob, not glob.glob: '[' in a path)."""
    if not path.is_dir():
        return 0
    if pattern.endswith("/"):
        return sum(1 for p in path.glob(pattern) if p.is_dir())
    return sum(1 for _ in path.glob(pattern))


def inventory(root: Path) -> dict:
    scripts = root / "scripts"
    dlc = root / "update/x64/dlcpacks"
    return {
        "asi": sorted(p.name for p in root.glob("*.asi")),
        "asi_loaders": sorted(p.name for p in root.glob("*.dll") if p.name.lower() in ("dinput8.dll", "dsound.dll", "xinput1_4.dll", "version.dll")),
        "shv": (root / "ScriptHookV.dll").is_file(),
        "shvdn": sorted(p.name for p in root.glob("ScriptHookVDotNet*.dll")),
        "scripts_files": _count(scripts, "*") if scripts.is_dir() else 0,
        "scripts_folders": _count(scripts, "*/") if scripts.is_dir() else 0,
        "dlcpacks": _count(dlc, "*/") if dlc.is_dir() else 0,
        "mods_folder": (root / "mods").is_dir(),
        "args_txt": (root / "args.txt").read_text(encoding="utf-8", errors="replace").strip() if (root / "args.txt").is_file() else None,
        "openiv": (root / "OpenIV.asi").is_file(),
    }