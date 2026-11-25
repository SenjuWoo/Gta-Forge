"""gtaforge command line. Every command prints one JSON object.

Exit codes: 0 ok, 1 findings (check/validate/doctor found problems), 2 named failure (bad input, missing
tool, with a fix), 3 bug (traceback included), 130 interrupted.
"""
from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

from . import __version__
from .util import ForgeError, emit


class _Parser(argparse.ArgumentParser):
    """argparse that raises instead of exiting, so bad usage is a JSON exit-2 answer, not a crash."""

    def error(self, message):
        raise ForgeError(f"usage: {message}", f"gtaforge {self.prog.split(' ', 1)[-1]} --help")


def _game(args, required: bool = True):
    from .game import find_game, require_game
    if required:
        return require_game(getattr(args, "game", None))
    root, _how, _c = find_game(getattr(args, "game", None))
    return root


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
                if a.dest == "help":
                    continue
                opts.append({"name": a.option_strings[0] if a.option_strings else a.dest,
                             "required": bool(a.required) or not a.option_strings,
                             "choices": list(a.choices) if a.choices else None, "help": a.help or ""})
            cmds.append({"command": name, "help": sub.description or "", "args": opts})
    return {"forge": "GTA Forge", "version": __version__, "commands": cmds,
            "global": ["--game <folder>", "--project <folder>"],
            "exit_codes": {"0": "ok", "1": "findings", "2": "named failure", "3": "bug", "130": "interrupted"}}, 0


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
    from .game import frameworks, game_version, inventory
    root = _game(args)
    return {"root": str(root), "version": game_version(root), "frameworks": frameworks(root), "inventory": inventory(root)}, 0


def cmd_natives(args):
    from .natives import header, search
    if args.header:
        return header(Path(args.header)), 0
    if not args.query:
        raise ForgeError("pass a native name, part, namespace or 0xhash", "gtaforge natives TASK_PLAY_ANIM")
    r = search(args.query, args.limit, ns=args.ns)
    return r, 0


def cmd_anim(args):
    from .anims import lookup
    if args.dict:
        return lookup(dict_name=args.dict, clip=args.clip, limit=args.limit), 0
    return lookup(pattern=args.pattern, limit=args.limit), 0


def cmd_rpf(args):
    from .rpf import run
    return run(args), 0


def cmd_index(args):
    from .index import build, find
    if args.action == "build":
        return build(_game(args), workers=args.workers, limit=args.limit_archives), 0
    if not args.query:
        raise ForgeError("pass a name", "gtaforge index find <name>")
    r = find(args.query, _game(args, required=False), limit=args.limit, ext=args.ext)
    return r, 0


def cmd_find(args):
    from .index import find
    r = find(args.query, _game(args, required=False), limit=args.limit, ext=args.ext)
    return r, (0 if r["found"] or r["partial_count"] else 1)


def cmd_script(args):
    from .scripts import run
    r = run(args)
    return r, (1 if r.get("errors") else 0)


def cmd_check(args):
    from .check import run
    game = _game(args) if args.require_game else _game(args, required=False)
    return run(_project(args), compile_=args.compile, game=game)


def cmd_compile(args):
    from .compilemod import run
    r = run(_project(args), _game(args, required=False))
    return r, (0 if r["ok"] else 1)


def cmd_build(args):
    from .build import run
    return run(_project(args), _game(args, required=False), target=args.target, encryption=args.encryption)


def cmd_new(args):
    from .project import create
    return create(args.name, args.folder, kinds=args.kind, game=args.target_game, force=args.force), 0


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
    return run(_project(args), _game(args), remove_=args.remove, dry_run=args.dry_run), 0


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
    from .util import hash_file, joaat
    if args.joaat:
        return {"joaat": [{"text": t, "hex": "0x" + joaat(t), "unsigned": int(joaat(t), 16),
                           "signed": int(joaat(t), 16) - (1 << 32) if int(joaat(t), 16) >= 1 << 31 else int(joaat(t), 16)}
                          for t in args.joaat]}, 0
    if not args.path:
        raise ForgeError("pass a file or --joaat <text>", "gtaforge hash --joaat adder")
    return hash_file(Path(args.path)), 0


def cmd_menyoo(args):
    from .menyoo import run
    return run(args), 0


def cmd_vi(args):
    from .vi import run
    return run(args), 0


def cmd_bindings(args):
    from .bindings import check
    return check(Path(args.keys), Path(args.table), _game(args, required=False), use_index=not args.no_index)


def parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--game", help="game folder (default: discovery: GTA5_ROOT, Steam, Rockstar, Epic)")
    common.add_argument("--project", help="mod project folder (default: current folder or a parent with gtaforge.json)")
    p = _Parser(prog="gtaforge", description="Local-first GTA V / GTA VI mod toolkit (JSON output)", parents=[common])
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True, parser_class=_Parser)

    def add(name, fn, help_):
        sp = sub.add_parser(name, help=help_, description=help_, parents=[common])
        sp.set_defaults(fn=fn)
        return sp

    add("doctor", cmd_doctor, "health: CLI, payload, game, build toolchain, archive keys, asset index, GTA VI").add_argument(
        "--require-game", action="store_true")
    add("capabilities", cmd_capabilities, "every command and option of this version")
    add("plan", cmd_plan, "route a request before writing").add_argument("request", nargs="+")
    add("knowledge", cmd_knowledge, "list or print a knowledge doc").add_argument("name", nargs="?")
    add("facts", cmd_facts, "query versioned domain facts").add_argument("key", nargs="?")
    add("game", cmd_game, "what is installed (read-only)")
    sp = add("natives", cmd_natives, "native DB (6,701 GTA V natives): name, part, namespace or 0xhash; --header writes natives.h")
    sp.add_argument("query", nargs="?")
    sp.add_argument("--ns", help="limit to a namespace (PED, TASK, ...)")
    sp.add_argument("--limit", type=int, default=25)
    sp.add_argument("--header", metavar="OUT", help="write a current natives.h for the ScriptHookV SDK")
    sp = add("anim", cmd_anim, "animation dict / clip lookup in the anim index (Menyoo list or GTA 6.5 data)")
    sp.add_argument("--dict")
    sp.add_argument("--clip")
    sp.add_argument("--pattern")
    sp.add_argument("--limit", type=int, default=30)
    sp = add("rpf", cmd_rpf, "archives: doctor, keys, info, list, find, extract (python for OPEN, ragekit for NG), pack (OPEN RPF7)")
    sp.add_argument("action", choices=["doctor", "keys", "info", "list", "find", "extract", "pack"])
    sp.add_argument("target", nargs="?")
    sp.add_argument("--pattern")
    sp.add_argument("--out")
    sp.add_argument("--nested", action="store_true", help="descend into archives inside the archive")
    sp.add_argument("--limit", type=int, default=500)
    sp.add_argument("--engine", choices=["auto", "python", "ragekit", "6to5m"])
    sp.add_argument("--magic", help="CodeWalker magic.dat (keys); default: extracted from the staged CodeWalker")
    sp.add_argument("--encryption", choices=["open", "none"], help="pack: archive flag (default open)")
    sp.add_argument("--store", action="store_true", help="pack: no compression")
    sp = add("index", cmd_index, "asset index of the installed game (build once, then find)")
    sp.add_argument("action", choices=["build", "find"])
    sp.add_argument("query", nargs="?")
    sp.add_argument("--workers", type=int, default=4)
    sp.add_argument("--limit-archives", type=int)
    sp.add_argument("--ext", help="limit to an extension (.ycd, .ydr, .ytd, ...)")
    sp.add_argument("--limit", type=int, default=50)
    sp = add("find", cmd_find, "is this asset in the game? (anim dict, model, texture... via the asset index)")
    sp.add_argument("query")
    sp.add_argument("--ext")
    sp.add_argument("--limit", type=int, default=50)
    sp = add("script", cmd_script, "script projects: info, check (natives, args, entry point, XML), lua syntax")
    sp.add_argument("action", choices=["info", "check", "lua"])
    sp.add_argument("target", nargs="?", default=".")
    sp = add("check", cmd_check, "validate a project: manifest, natives, Menyoo hashes, payload, optional compile")
    sp.add_argument("--compile", action="store_true")
    sp.add_argument("--require-game", action="store_true")
    add("compile", cmd_compile, "compile C++ (CMake + MSVC) and C# (dotnet, SHVDN3) into build/ and bin/")
    sp = add("build", cmd_build, "compile native code and pack <name>.rpf folders into build/")
    sp.add_argument("--target", default="auto", choices=["auto", "native", "archive"])
    sp.add_argument("--encryption", default="open", choices=["open", "none", "ng", "aes"])
    sp = add("new", cmd_new, "start a project from templates (repeat --kind: cpp shvdn menyoo xml lua)")
    sp.add_argument("name")
    sp.add_argument("--folder")
    sp.add_argument("--kind", action="append", default=[])
    sp.add_argument("--target-game", choices=["auto", "legacy", "enhanced", "both"], default="auto")
    sp.add_argument("--force", action="store_true")
    add("bump", cmd_bump, "bump the project version (manifest, CHANGELOG, csproj)").add_argument("part", choices=["patch", "minor", "major"])
    add("package", cmd_package, "deterministic runtime zip (payload only) + receipt").add_argument("--out")
    add("validate", cmd_validate, "check a built zip (paths, runtime-only, no framework files, secrets)").add_argument("archive")
    sp = add("deploy", cmd_deploy, "install / remove the payload in the game for testing (receipt + original backups)")
    sp.add_argument("--remove", action="store_true")
    sp.add_argument("--dry-run", action="store_true")
    sp = add("logs", cmd_logs, "read ScriptHookV / SHVDN / asi / game logs at once")
    sp.add_argument("--mod")
    sp.add_argument("--limit", type=int, default=200)
    add("conflicts", cmd_conflicts, "mods fighting over the same files or script names")
    add("nexus", cmd_nexus, "Nexus page kit (description, changelog, BBCode); no upload")
    sp = add("hash", cmd_hash, "file SHA-256, or joaat of names (--joaat a b c)")
    sp.add_argument("path", nargs="?")
    sp.add_argument("--joaat", nargs="+", metavar="TEXT")
    sp = add("menyoo", cmd_menyoo, "Menyoo lists: index, search anims/props/peds/speech/cutscenes, stats")
    sp.add_argument("action", choices=["index", "search", "stats"])
    sp.add_argument("query", nargs="?")
    sp.add_argument("--list", choices=["anim", "prop", "ped", "speech", "cutscene"])
    sp.add_argument("--folder")
    sp.add_argument("--out")
    sp.add_argument("--limit", type=int, default=50)
    sp = add("vi", cmd_vi, "GTA VI kit: status, watch (GitHub), tools, build-6to5m, probe <folder>, names <hashes>, checklist [folder], extract <rpf>")
    sp.add_argument("action", choices=["status", "watch", "tools", "build-6to5m", "probe", "names", "checklist", "extract"])
    sp.add_argument("target", nargs="?")
    sp.add_argument("--out")
    sp.add_argument("--words", action="append", help="names: candidate wordlist (repeat)")
    sp.add_argument("--no-index", action="store_true", help="names: do not add the GTA V asset index as candidates")
    sp.add_argument("--list", action="store_true", help="extract: list only")
    sp.add_argument("--limit", type=int)
    sp = add("bindings", cmd_bindings, "binding-table coverage: every content key resolves to an asset in the game")
    sp.add_argument("keys", help="binding keys JSON")
    sp.add_argument("table", help="per-game bindings JSON")
    sp.add_argument("--no-index", action="store_true")
    return p


def main(argv=None) -> int:
    t0 = time.time()
    try:
        args = parser().parse_args(argv)
        payload, code = args.fn(args)
    except ForgeError as e:
        emit({"ok": False, "error": str(e), "fix": e.fix, "exit": e.code})
        return e.code
    except OSError as e:  # the environment (permissions, disk, locked file), not a forge bug
        emit({"ok": False, "error": f"{type(e).__name__}: {e}", "fix": "check the path, permissions and free space; close programs holding the file", "exit": 2})
        return 2
    except SystemExit as e:  # --help / --version print and exit 0
        return int(e.code or 0) if isinstance(e.code, int) else 0
    except KeyboardInterrupt:
        emit({"ok": False, "error": "interrupted", "exit": 130})
        return 130
    except Exception:  # a bug, not bad input
        emit({"ok": False, "error": "internal error (a forge bug)", "traceback": traceback.format_exc()[-4000:], "exit": 3,
              "report": "python TOOLS/field_report.py gta-forge --title ... in the AI bundle"})
        return 3
    if isinstance(payload, dict):
        payload.setdefault("ok", code == 0)
        payload["seconds"] = round(time.time() - t0, 3)
    emit(payload)
    return code


if __name__ == "__main__":
    sys.exit(main())
