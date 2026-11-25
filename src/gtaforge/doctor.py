"""Health check. Sections: cli, payload, game, build toolchain, archive tools + keys, asset index, GTA VI.

Exit: 0 healthy, 1 findings, 2 the --game passed is not a game folder.
"""
from __future__ import annotations

import json
import platform
import sys

from . import __version__
from .game import edition, find_game, find_vi, frameworks, game_version, inventory
from .project import templates
from .util import KNOWLEDGE_DIR, TEMPLATES_DIR, ForgeError, find_tool, home_dir, msvc_install, tools

REQUIRED_KNOWLEDGE = ("facts.json", "frameworks.json", "routes.json", "errors.json", "tools.json", "vi.json")
CORE = ("scripthookv", "asi_loader")


def _payload() -> tuple[dict, list]:
    bad = []
    for name in REQUIRED_KNOWLEDGE:
        try:
            json.loads((KNOWLEDGE_DIR / name).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            bad.append(f"{name}: {e}")
    try:
        from .natives import _db
        n_natives = len(_db())
    except (ForgeError, OSError, ValueError) as e:
        n_natives = 0
        bad.append(f"natives.json.gz: {e}")
    routes = json.loads((KNOWLEDGE_DIR / "routes.json").read_text(encoding="utf-8")) if not bad else {"routes": []}
    for r in routes.get("routes", []):
        for d in r.get("docs", []):
            if not (KNOWLEDGE_DIR / d).is_file():
                bad.append(f"route {r['id']} names missing doc {d}")
    tpls = templates() if TEMPLATES_DIR.is_dir() else {}
    if not tpls:
        bad.append("templates/ missing or empty")
    return {"status": "ok" if not bad else "fail", "templates": sorted(tpls), "natives": n_natives,
            "knowledge_docs": len(list(KNOWLEDGE_DIR.glob("*.md"))), "problems": bad}, bad


def run(game_arg: str | None = None, require_game: bool = False) -> tuple[dict, int]:
    report: dict = {"forge": {"version": __version__, "python": platform.python_version(), "platform": sys.platform,
                              "home": str(home_dir())}}
    problems: list[dict] = []
    py_ok = sys.version_info >= (3, 10)
    report["cli"] = {"status": "ok" if py_ok else "fail", "python_3_10_plus": py_ok}
    if not py_ok:
        problems.append({"section": "cli", "problem": "Python 3.10+ required", "fix": "install Python 3.10 or newer"})
    report["payload"], bad = _payload()
    if bad:
        problems.append({"section": "payload", "problem": "; ".join(bad), "fix": "git checkout / reinstall the forge"})

    try:
        root, how, checked = find_game(game_arg)
    except ForgeError as e:
        root, how, checked = None, "", [str(e)]
    if root is None:
        report["game"] = {"status": "missing", "checked": checked,
                          "fix": "pass --game <folder with GTA5_Enhanced.exe or GTA5.exe> or set GTA5_ROOT"}
        if require_game or game_arg:
            problems.append({"section": "game", "problem": "game not found", "fix": report["game"]["fix"]})
    else:
        fws = frameworks(root)
        missing_core = [f["id"] for f in fws if f["id"] in CORE and not f["installed"]]
        gv = game_version(root)
        inv = inventory(root)
        warn = []
        if gv.get("file_version") and gv.get("shv_supported") is False:
            warn.append({"problem": f"ScriptHookV does not support {gv['file_version']} (supports {', '.join(gv['shv_supports'])}; "
                                    f"checked {gv.get('shv_checked')})",
                         "fix": "asi mods cannot load on this build: wait for a ScriptHookV update or use a supported copy (knowledge rig)"})
        if gv.get("note"):
            warn.append({"problem": gv["note"], "fix": "add the version to knowledge/facts.json game.versions"})
        has_mods = bool(inv["asi"] or inv["shv"])
        if has_mods and gv.get("edition") == "enhanced" and "-nobattleye" not in (inv.get("args_txt") or ""):
            warn.append({"problem": "mods installed but args.txt lacks -nobattleye (BattlEye blocks asi in Enhanced)",
                         "fix": "add -nobattleye to args.txt, story mode only"})
        status = "ok" if not missing_core and not warn else "warn"
        report["game"] = {"status": status, "root": str(root), "found_by": how, "version": gv, "frameworks": fws,
                          "missing_core": missing_core, "warnings": warn, "inventory": inv}
        if missing_core:
            problems.append({"section": "game", "problem": "missing core: " + ", ".join(missing_core),
                             "fix": "install ScriptHookV + its dinput8.dll (gtaforge knowledge frameworks); story mode only"})
        for w in warn:
            problems.append({"section": "game", **w})

    msvc = msvc_install()
    sdk = find_tool("shv_sdk")
    report["build"] = {"msvc": msvc, "cmake": find_tool("cmake"), "ninja": find_tool("ninja"), "dotnet": find_tool("dotnet"),
                       "shv_sdk": sdk, "shvdn_ref": find_tool("shvdn_ref"),
                       "cpp_ready": bool(msvc and msvc.get("vcvars64") and sdk and find_tool("cmake")),
                       "note": "C++ asi needs MSVC + CMake + the SDK; SHVDN needs dotnet + ScriptHookVDotNet3.dll"}
    from .rpf import keys_state
    ks = keys_state()
    report["archives"] = {"ragekit": find_tool("ragekit"), "codewalker": find_tool("codewalker"), "6ixpack": find_tool("6to5m"),
                          "keys": ks, "fix": None if ks["ng"] or not root else "gtaforge rpf keys"}
    try:
        from .index import current_index
        idx = current_index(root)
        meta = idx.with_suffix("").with_suffix(".json")
        report["index"] = {"file": str(idx), **({k: v for k, v in json.loads(meta.read_text(encoding="utf-8")).items()
                                                  if k in ("entries", "archives", "built")} if meta.is_file() else {})}
    except ForgeError as e:
        report["index"] = {"file": None, "fix": e.fix}
    report["vi"] = {"folders": find_vi(), "6ixpack": find_tool("6to5m"),
                    "note": "no PC-runnable GTA VI is known; vi probe works on any folder or dump"}
    report["tools"] = tools()
    report["problems"] = problems
    report["ok"] = not problems
    if problems:
        report["fix"] = problems[0]["fix"]
    return report, (0 if not problems else (2 if game_arg and root is None else 1))
