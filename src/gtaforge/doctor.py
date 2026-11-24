"""Health check. CLI health, forge payload, game discovery and toolchain are separate sections."""
from __future__ import annotations

import os
import platform
import sys

from . import __version__
from .game import find_game, frameworks, game_version, inventory, edition
from .project import templates
from .util import KNOWLEDGE_DIR, TEMPLATES_DIR, ForgeError, home_dir, tools

REQUIRED_KNOWLEDGE = ("facts.json", "frameworks.json", "routes.json", "errors.json", "tools.json", "natives.json")
CORE = ("scripthookv", "asi_loader")


def run(game_arg: str | None = None, require_game: bool = False) -> tuple[dict, int]:
    import json
    report: dict = {"forge": {"version": __version__, "python": platform.python_version(), "platform": sys.platform,
                              "home": str(home_dir())}}
    problems = []
    py_ok = sys.version_info >= (3, 10)
    report["cli"] = {"status": "ok" if py_ok else "fail", "python_3_10_plus": py_ok}
    if not py_ok:
        problems.append({"section": "cli", "problem": "Python 3.10+ required", "fix": "install Python 3.10 or newer"})
    payload_bad = []
    for name in REQUIRED_KNOWLEDGE:
        try:
            json.loads((KNOWLEDGE_DIR / name).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            payload_bad.append(f"{name}: {e}")
    tpls = templates() if TEMPLATES_DIR.is_dir() else {}
    if not tpls:
        payload_bad.append("templates/ missing or empty")
    report["payload"] = {"status": "ok" if not payload_bad else "fail", "templates": sorted(tpls),
                         "knowledge_docs": len(list(KNOWLEDGE_DIR.glob("*.md"))), "problems": payload_bad}
    if payload_bad:
        problems.append({"section": "payload", "problem": "; ".join(payload_bad), "fix": "git checkout / reinstall the forge"})
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
        ed = edition(root)
        warn = []
        gv = game_version(root)
        if gv.get("file_version") and gv.get("shv_supported") is False:
            warn.append({"problem": f"ScriptHookV does not list {gv['file_version']} (supports {gv['shv_supported']})",
                         "fix": "use a supported build for the rig; see knowledge/rig.md"})
        report["game"] = {"status": "ok" if not missing_core and not warn else "warn", "root": str(root), "found_by": how,
                          "version": gv, "frameworks": fws, "missing_core": missing_core, "warnings": warn,
                          "inventory": inventory(root)}
        if missing_core:
            problems.append({"section": "game", "problem": "missing core: " + ", ".join(missing_core),
                             "fix": "install ScriptHookV + an asi loader (knowledge/frameworks.md); never in GTA Online"})
    report["tools"] = tools()
    report["tools_note"] = ("optional: CodeWalker / ragekit / 6to5m read archives, cmake+MSVC builds C++, dotnet builds SHVDN, "
                            "luajit checks Lua; file versions need Windows")
    report["problems"] = problems
    report["ok"] = not problems
    return report, (0 if not problems else (2 if game_arg and root is None else 1))