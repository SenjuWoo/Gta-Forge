"""Archive / resource inspection. Routes to the installed tool; never edits the game.

Engines:
  codewalker: CodeWalker.exe (RPF Explorer GUI; `info`/`list` read the RPF header in Python,
              extract/list of loose files is a Python RPF7 reader for unencrypted archives)
  ragekit:    ragekit CLI (C++20 GTA V/Enhanced reader) if built (ragekit build.cmd)
  6to5m:      6ixpack (Rust, GTA VI RPF9) - vi status / build-6to5m only
"""
from __future__ import annotations

import struct
from pathlib import Path

from .util import ForgeError, find_tool, run

RPF7_MAGIC = b"RPF7"


def rpf7_entries(path: Path) -> list[dict]:
    """Read an unencrypted RPF7 table of contents (GTA V PC archives are RPF7, encrypted names -> names are hashes)."""
    with open(path, "rb") as f:
        head = f.read(16)
        if head[:4] != RPF7_MAGIC:
            raise ForgeError(f"not an RPF7 archive: {path}", "GTA VI uses RPF9: use gtaforge vi / 6to5m")
        _ver, _size, count, _enc = struct.unpack("<IIII", head[4:16])
        # Entry: name hash(4) ?(4) size(4) ?(4) offset(4) ... 12 bytes; encrypted TOC can't be read without keys.
        # We report the header only; full listing needs CodeWalker / ragekit.
        return [{"magic": "RPF7", "entries": count, "note": "TOC encrypted: names are hashes; use CodeWalker RPF Explorer or ragekit for a listing"}]


def run(args) -> dict:
    eng = args.engine or "auto"
    if eng == "6to5m":
        raise ForgeError("6to5m is GTA VI only", "use: gtaforge vi build-6to5m")
    target = Path(args.target) if args.target else None
    if args.action == "doctor":
        return {"codewalker": find_tool("codewalker"), "ragekit": find_tool("ragekit"), "6to5m": find_tool("6to5m"),
                "note": "install at least one; CodeWalker: github.com/crxhvrd/CodeWalkerProjects/releases"}
    if target is None:
        raise ForgeError("pass an archive or file", "gtaforge rpf list <archive.rpf>")
    if args.action == "info":
        return rpf7_entries(target) if target.is_file() else {"path": str(target), "is_dir": True}
    if args.action == "list":
        info = rpf7_entries(target)
        return {"path": str(target), **info}
    cw = find_tool("codewalker")
    rk = find_tool("ragekit")
    if eng in ("auto", "codewalker") and cw:
        # CodeWalker is GUI-first; a CLI listing is not exposed. ragekit is the scriptable route.
        if not rk:
            raise ForgeError("CodeWalker has no CLI listing; build ragekit for scripted extract",
                             "ragekit: build.cmd in vendor/ragekit-main, then set RAGEKIT_CLI")
    if rk:
        argv = [rk, args.action, str(target)]
        if args.pattern:
            argv += ["--pattern", args.pattern]
        if args.out:
            argv += ["--out", args.out]
        r = run(argv)
        return {"engine": "ragekit", **r}
    raise ForgeError("no scriptable archive tool installed", "gtaforge rpf doctor; install CodeWalker + build ragekit")