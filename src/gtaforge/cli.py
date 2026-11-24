"""gtaforge command line. Every command prints JSON; exit 0 = ok, 1 = findings, 2 = named failure, 3 = bug."""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

from . import __version__
from .util import ForgeError, emit


def _game(args):
    from .game import require_game
    return require_game(getattr(args, "game", None))


def _project(args):
    from .project import find_project
    return find_project(getattr(args, "project", None))


def cmd_doctor(args):
    from .doctor import run
    return run(args.game, args.require_game)


def cmd_capabilities(args):
    p = parser()
    cmds = []
    for action in p._subparsers._group_actions:  # generated from the parser, never a hand-kept list
        for name, sub in action.choices.items():
            opts = []
            for a in sub._actions:
                if a.dest in ("help",):
                    continue
                opts.append({"name": a.option_strings[0] if a.option_strings else a.dest,
                             "required": bool(a.required) or not a.option_strings, "help": a.help or ""})
            cmds.append({"command": name, "help": sub.description or "", "args": opts})
    return {"forge": "GTA Forge", "version": __version__, "commands": cmds,
            "global": ["--game <folder>", "--project <folder>"],
            "exit_codes": {"0": "ok", "1": "findings", "2": "named failure", "3": "bug"}}, 0


def cmd_plan(args):
    from .knowledge import plan
    return plan(" ".join(args.request)), 0


def cmd_knowledge(args):
    from .knowledge import doc, docs
    if args.name:
        return {"name": args.name, "text": doc(args.name)}, 0
    return {"docs": docs(), "hint": "gtaforge knowledge <name>"}, 0


def cmd_facts(args):
    from .knowledge import facts
    return {"facts": facts(args.key)}, 0


def cmd_game(args):
    from .game import inventory, require_game, game_version
    from .util import tools
    root = _game(args)
    return {"root": str(root), "version": game_version(root), "inventory": inventory(root), "tools": tools()}, 0


def cmd_natives(args):
    from .natives import search
    return search(args.query, args.limit), 0


def cmd_anim(args):
    from .anims import lookup
    if args.dict:
        return lookup(dict_name=args.dict, clip=args.clip, game=args.game), 0
    return lookup(pattern=args.pattern, game=args.game, limit=args.limit), 0


def cmd_rpf(args):
    from .rpf import run as rpf_run
    return rpf_run(args), 0


def cmd_script(args):
    from .scripts import run as script_run
    return script_run(args), 0


def cmd_check(args):
    from .check import run
    return run(_project(args), compile_=args.compile, game=_game(args) if args.require_game else None)


def cmd_compile(args):
    from .compilemod import run
    return run(_project(args), _game(args)), 0


def cmd_build(args):
    from .build import run
    return run(_project(args), _game(args), target=args.target)


def cmd_new(args):
    from .project import create
    return create(args.name, args.folder, kinds=args.kind, game=args.game, force=args.force), 0


def cmd_bump(args):
    from .project import bump
    return bump(_project(args), args.part), 0


def cmd_package(args):
    from .package import run
    return run(_project(args), out=args.out), 0


def cmd_validate(args):
    from .package import validate
    return validate(Path(args.archive))


def cmd_deploy(args):
    from .deploy import run
    return run(_project(args), _game(args), remove=args.remove), 0


def cmd_logs(args):
    from .logs import run
    return run(_game(args), mod=args.mod, limit=args.limit), 0


def cmd_conflicts(args):
    from .conflicts import run
    return run(_project(args), _game(args)), 0


def cmd_nexus(args):
    from .nexus import run
    return run(_project(args)), 0


def cmd_hash(args):
    from .util import hash_file
    if args.tweakdb:
        from .knowledge import tweakdb_id
        return {"record": args.tweakdb, "id": tweakdb_id(args.tweakdb)}, 0
    return hash_file(Path(args.path)), 0


def cmd_menyoo(args):
    from .menyoo import run
    return run(args), 0


def cmd_vi(args):
    from .vi import run
    return run(args), 0


def parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--game", help="game folder (default: discovery, env GTA5_ROOT)")
    common.add_argument("--project", help="mod project folder (default: current folder)")
    p = argparse.ArgumentParser(prog="gtaforge", description="Local-first GTA V / GTA VI mod toolkit (JSON output)", parents=[common])
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        sp = sub.add_parser(name, help=help_, description=help_, parents=[common])
        sp.set_defaults(fn=fn)
        return sp

    add("doctor", cmd_doctor, "health: CLI, payload, game, frameworks, tools (separate sections)").add_argument("--require-game", action="store_true")
    add("capabilities", cmd_capabilities, "every command and option of this version")
    add("plan", cmd_plan, "route a request before writing").add_argument("request", nargs="+")
    add("knowledge", cmd_knowledge, "list or print a knowledge doc").add_argument("name", nargs="?")
    add("facts", cmd_facts, "query versioned domain facts").add_argument("key", nargs="?")
    add("game", cmd_game, "what is installed (read-only)")
    sp = add("natives", cmd_natives, "search the native DB (name, hash, return, params)"); sp.add_argument("query"); sp.add_argument("--limit", type=int, default=25)
    sp = add("anim", cmd_anim, "animation dictionary / clip lookup (GTA V index, Menyoo list)"); sp.add_argument("--dict"); sp.add_argument("--clip"); sp.add_argument("--pattern"); sp.add_argument("--limit", type=int, default=30)
    sp = add("rpf", cmd_rpf, "archive / resource inspection via CodeWalker, ragekit or 6to5m"); sp.add_argument("action", choices=["doctor", "list", "find", "extract", "info"]); sp.add_argument("target", nargs="?"); sp.add_argument("--pattern"); sp.add_argument("--out"); sp.add_argument("--engine", choices=["auto", "codewalker", "ragekit", "6to5m"])
    sp = add("script", cmd_script, "script projects: info, native-stub check, Lua syntax, SHVDN refs"); sp.add_argument("action", choices=["info", "check", "lua"]); sp.add_argument("target", nargs="?", default=".")
    sp = add("check", cmd_check, "validate a project against the manifest and the installed game")
    sp.add_argument("--compile", action="store_true")
    sp.add_argument("--require-game", action="store_true")
    add("compile", cmd_compile, "compile C++ (CMake) or C# (dotnet) script projects in a scratch copy")
    sp = add("build", cmd_build, "build a native plugin (CMake) or pack an archive (CodeWalker)"); sp.add_argument("--target", default="auto")
    sp = add("new", cmd_new, "start a project from templates (repeat --kind; --game legacy|enhanced|both)"); sp.add_argument("name"); sp.add_argument("--folder"); sp.add_argument("--kind", action="append", default=[]); sp.add_argument("--force", action="store_true")
    sp = add("bump", cmd_bump, "bump version everywhere, keep the last good package").add_argument("part", choices=["patch", "minor", "major"])
    sp = add("package", cmd_package, "deterministic runtime zip + receipt").add_argument("--out")
    sp = add("validate", cmd_validate, "check a built zip (layout, secrets, runtime-only)").add_argument("archive")
    sp = add("deploy", cmd_deploy, "install / remove in the game for testing (receipt + backups)").add_argument("--remove", action="store_true")
    sp = add("logs", cmd_logs, "read ScriptHookV / SHVDN / asi / game logs at once")
    sp.add_argument("--mod")
    sp.add_argument("--limit", type=int, default=200)
    add("conflicts", cmd_conflicts, "mods fighting over the same files, natives or anim dicts")
    add("nexus", cmd_nexus, "Nexus page kit (description, changelog, BBCode)")
    sp = add("hash", cmd_hash, "file SHA-256 or a TweakDB-style id"); sp.add_argument("path", nargs="?"); sp.add_argument("--tweakdb")
    sp = add("menyoo", cmd_menyoo, "Menyoo lists: index, search anims/props/peds/speech/cutscenes"); sp.add_argument("action", choices=["index", "search", "stats"]); sp.add_argument("query", nargs="?"); sp.add_argument("--list", choices=["anim", "prop", "ped", "speech", "cutscene"]); sp.add_argument("--folder"); sp.add_argument("--out"); sp.add_argument("--limit", type=int, default=50)
    sp = add("vi", cmd_vi, "GTA VI readiness (no game needed): tool watch, RPF9 index, 6to5m build check"); sp.add_argument("action", choices=["status", "tools", "build-6to5m"])
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    t0 = time.time()
    try:
        payload, code = args.fn(args)
    except ForgeError as e:
        emit({"ok": False, "error": str(e), "fix": e.fix, "exit": e.code})
        return e.code
    except KeyboardInterrupt:
        emit({"ok": False, "error": "interrupted", "exit": 130})
        return 130
    except Exception:  # a bug, not bad input
        emit({"ok": False, "error": "internal error", "traceback": traceback.format_exc()[-4000:], "exit": 3})
        return 3
    if isinstance(payload, dict):
        payload.setdefault("ok", code == 0)
        payload["seconds"] = round(time.time() - t0, 3)
    emit(payload)
    return code


if __name__ == "__main__":
    sys.exit(main())