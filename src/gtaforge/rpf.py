"""Archive inspection and packing. Read-only on the game; writes only where --out points.

Routes, in order:
  python   - header of any RPF7; full list/find/extract of NONE/OPEN archives (mod dlc.rpf,
             FiveM resource.rpf); `pack` writes OPEN archives (rpf7.py)
  ragekit  - NG/AES archives of the installed game (`ragekit rpf ls|extract|cat`), after `rpf keys`
             derives the keys from the game exe + CodeWalker's magic.dat
  6ixpack  - GTA VI RPF9 (gtaforge vi ...)
"""
from __future__ import annotations

import os
from pathlib import Path

from . import rpf7
from .util import ForgeError, find_tool, home_dir, run_proc

KEY_FILES = ("gtav_aes_key.dat", "gtav_ng_key.dat", "gtav_ng_decrypt_tables.dat", "gtav_hash_lut.dat")


def keys_dir() -> Path:
    env = os.environ.get("RAGEKIT_KEYS")
    return Path(env) if env else Path.home() / ".ragekit" / "keys"


def keys_state() -> dict:
    d = keys_dir()
    have = {k: (d / k).is_file() for k in KEY_FILES}
    return {"folder": str(d), "aes": have["gtav_aes_key.dat"], "ng": all(have.values()), "files": have}


def magic_dat(explicit: str | None = None) -> Path | None:
    """CodeWalker's magic.dat: an explicit file, a cached copy, or extracted from CodeWalker.Core.dll."""
    if explicit:
        p = Path(explicit)
        if not p.is_file():
            raise ForgeError(f"no magic.dat: {p}", "pass CodeWalker's magic.dat or omit --magic")
        return p
    cached = home_dir() / "keys" / "magic.dat"
    if cached.is_file():
        return cached
    cw = find_tool("codewalker")
    if not cw:
        return None
    core = Path(cw).parent / "CodeWalker.Core.dll"
    if not core.is_file() or os.name != "nt":
        return None
    cached.parent.mkdir(parents=True, exist_ok=True)
    # magic.dat is the "magic" byte[] of CodeWalker.Core.Properties.Resources (read with .NET, no code from it runs).
    ps = ("$a=[Reflection.Assembly]::LoadFrom($env:GTAF_CORE);"
          "$s=$a.GetManifestResourceStream('CodeWalker.Core.Properties.Resources.resources');"
          "$r=New-Object System.Resources.ResourceReader($s);$e=$r.GetEnumerator();"
          "while($e.MoveNext()){if($e.Key -eq 'magic'){[IO.File]::WriteAllBytes($env:GTAF_OUT,[byte[]]$e.Value)}}")
    run_proc(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], timeout=120,
             env={"GTAF_CORE": str(core), "GTAF_OUT": str(cached)})
    return cached if cached.is_file() else None


def _ragekit() -> str | None:
    return find_tool("ragekit")


def _edition_flag(path: Path, game: Path | None) -> str:
    for root in [game, *path.resolve().parents]:
        if root and (root / "GTA5_Enhanced.exe").is_file():
            return "--enhanced"
        if root and (root / "GTA5.exe").is_file():
            return "--legacy"
    return "--enhanced"


def _rk_run(argv: list[str], timeout: int = 1800) -> dict:
    r = run_proc(argv, timeout=timeout)
    if r["timed_out"]:
        raise ForgeError("ragekit timed out", "narrow the path or raise the timeout")
    if r["code"]:
        err = (r["stderr"] or r["stdout"]).strip().splitlines()
        msg = err[-1] if err else f"exit {r['code']}"
        fix = "gtaforge rpf keys (derives NG keys from the game exe)" if "keys" in msg.lower() else "see ragekit --help"
        raise ForgeError(f"ragekit: {msg}", fix)
    return r


def parse_tsv(text: str) -> list[dict]:
    """ragekit `rpf ls -r --tsv` rows: kind (D/B/R), path, size, stored, ... (other stdout lines are skipped)."""
    kinds = {"D": "dir", "B": "bin", "R": "rsc"}
    out = []
    for line in text.splitlines():
        cols = line.rstrip("\r").split("\t")
        if len(cols) < 3 or cols[0] not in kinds or not cols[1]:
            continue
        item = {"path": cols[1], "kind": kinds[cols[0]]}
        if cols[0] != "D":
            item["size"] = int(cols[2]) if cols[2].isdigit() else None
            item["stored"] = int(cols[3]) if len(cols) > 3 and cols[3].isdigit() else None
        out.append(item)
    return out


def list_entries(target: Path, nested: bool = False, game: Path | None = None) -> tuple[str, list[dict], dict]:
    head = rpf7.read_header(target)
    if head["readable_here"]:
        arc = rpf7.Archive.open(target)
        items = [{"path": p, **{k: v for k, v in e.as_dict().items() if k != "path"}} for p, e, _a in arc.walk(nested)]
        return "python", items, head
    rk = _ragekit()
    if not rk:
        raise ForgeError(f"{target.name} is {head['encryption'].upper()} encrypted and ragekit is not installed",
                         "build ragekit (vendor/ragekit-main build.cmd) or set RAGEKIT_CLI; then gtaforge rpf keys")
    if not keys_state()["ng"] and head["encryption"] == "ng":
        raise ForgeError(f"{target.name} is NG encrypted and no NG keys exist in {keys_dir()}",
                         "gtaforge rpf keys  (reads the game exe + CodeWalker's magic.dat; keys stay on this PC)")
    argv = [rk, "rpf", "ls", str(target), "-r", "--tsv", _edition_flag(target, game)]
    if nested:
        argv.insert(5, "--nested")
    r = _rk_run(argv)
    return "ragekit", parse_tsv(r["stdout"]), head


def run(args) -> dict:
    action = args.action
    eng = getattr(args, "engine", None) or "auto"
    if eng == "6to5m":
        raise ForgeError("6to5m reads GTA VI RPF9 only", "gtaforge vi probe <folder> / gtaforge vi extract <file>")
    if action == "doctor":
        return {"ragekit": _ragekit(), "codewalker": find_tool("codewalker"), "6to5m": find_tool("6to5m"),
                "keys": keys_state(), "magic_dat": str(magic_dat()) if magic_dat() else None,
                "python": "header of any RPF7; list/extract/pack of NONE/OPEN archives",
                "fix": None if keys_state()["ng"] else "gtaforge rpf keys"}
    if action == "keys":
        rk = _ragekit()
        if not rk:
            raise ForgeError("ragekit not found", "build vendor/ragekit-main (build.cmd) or set RAGEKIT_CLI")
        from .game import require_game
        game = require_game(getattr(args, "game", None))
        exe = next((game / n for n in ("GTA5_Enhanced.exe", "GTA5.exe") if (game / n).is_file()), None)
        md = magic_dat(getattr(args, "magic", None))
        argv = [rk, "rpf", "keys", str(exe), str(keys_dir())] + (["--magic", str(md)] if md else [])
        r = _rk_run(argv, timeout=900)
        state = keys_state()
        return {"exe": str(exe), "magic_dat": str(md) if md else None, "keys": state,
                "log": r["stdout"].strip().splitlines()[-3:],
                "note": "keys are the game's own data: they stay in this folder, never in a repo or package",
                "fix": None if state["ng"] else "NG keys need CodeWalker's magic.dat: install CodeWalker or pass --magic"},
    target = Path(args.target) if args.target else None
    if action == "pack":
        if target is None or not args.out:
            raise ForgeError("pass a folder and --out <file.rpf>", "gtaforge rpf pack <folder> --out dlc.rpf")
        return rpf7.pack(target, Path(args.out), encryption=getattr(args, "encryption", None) or "open",
                         compress=not getattr(args, "store", False))
    if target is None:
        raise ForgeError("pass an archive", "gtaforge rpf list <archive.rpf>")
    if not target.is_file():
        raise ForgeError(f"no file: {target}", "pass an existing .rpf")
    if action == "info":
        from . import rpf9
        with open(target, "rb") as f:
            kind = rpf9.sniff(f.read(8))
        if kind == "rpf9":
            return rpf9.read(target, nested=False)
        return {"path": str(target), **rpf7.read_header(target), "keys": keys_state()}
    game = None
    if getattr(args, "game", None):
        from .game import require_game
        game = require_game(args.game)
    engine, items, head = list_entries(target, nested=getattr(args, "nested", False), game=game)
    pat = (args.pattern or "").lower()
    if action == "find" and not pat:
        raise ForgeError("pass --pattern <part>", "gtaforge rpf find x64b.rpf --pattern strip_club")
    hits = [i for i in items if pat in i["path"].lower()] if pat else items
    if action in ("list", "find"):
        limit = getattr(args, "limit", 500) or 500
        return {"path": str(target), "engine": engine, "encryption": head["encryption"], "entries": len(items),
                "matched": len(hits), "items": hits[:limit], "truncated": len(hits) > limit}
    if action == "extract":
        if not args.out:
            raise ForgeError("pass --out <folder>", "gtaforge rpf extract <archive> --out <folder> [--pattern part]")
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        files = [i for i in hits if i["kind"] != "dir"]
        if engine == "python":
            arc = rpf7.Archive.open(target)
            written = []
            nested = getattr(args, "nested", False)
            for _full, e, owner in arc.walk(nested):
                if e.kind == "dir" or (pat and pat not in _full.lower()):
                    continue
                if nested and e.name.lower().endswith(".rpf"):
                    continue  # its contents are written below <name>.rpf/ instead of the archive file
                dst = (out / _full).resolve()
                if out.resolve() not in dst.parents:
                    raise ForgeError(f"entry escapes the output folder: {_full}", "archive is malicious or damaged")
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(owner.extract(e))
                written.append(_full)
            return {"engine": "python", "out": str(out), "written": len(written), "files": written[:200]}
        rk = _ragekit()
        written = []
        for i in files:
            dst = (out / i["path"]).resolve()
            if out.resolve() not in dst.parents:
                raise ForgeError(f"entry escapes the output folder: {i['path']}", "archive is damaged")
            dst.parent.mkdir(parents=True, exist_ok=True)
            _rk_run([rk, "rpf", "cat", str(target), i["path"], str(dst), _edition_flag(target, game)])
            written.append(i["path"])
            if len(written) >= (getattr(args, "limit", 500) or 500):
                break
        return {"engine": "ragekit", "out": str(out), "written": len(written), "files": written[:200],
                "truncated": len(files) > len(written)}
    raise ForgeError(f"unknown action {action}", "doctor | keys | info | list | find | extract | pack")
