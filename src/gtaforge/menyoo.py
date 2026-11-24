"""Menyoo lists (PedAnimList.txt, PedSpeechList.txt, PropList.txt, PedList.xml, CutsceneLabels.txt).

index  -> dict -> clip JSON per topic in --out (default <home>/menyoo), usable as GTA_FORGE_ANIM_INDEX
search -> grep one list (anim: dict contains query, clips listed)
stats  -> counts
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .util import ForgeError, home_dir, save_json

LISTS = ("PedAnimList.txt", "PedSpeechList.txt", "PropList.txt", "PedList.xml", "CutsceneLabels.txt")


def _folder(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    import os
    if os.environ.get("MENYOO_STUFF"):
        return Path(os.environ["MENYOO_STUFF"])
    raise ForgeError("pass --folder <menyooStuff>", "the folder that holds PedAnimList.txt etc.")


def run(args) -> dict:
    folder = _folder(args.folder)
    if not folder.is_dir():
        raise ForgeError(f"no folder: {folder}", "pass --folder")
    if args.action == "stats":
        return {name: {"exists": (folder / name).is_file(), "bytes": (folder / name).stat().st_size if (folder / name).is_file() else 0} for name in LISTS}
    if args.action == "index":
        pairs: dict[str, set] = {}
        for line in (folder / "PedAnimList.txt").read_text(encoding="utf-8", errors="replace").splitlines():
            p = line.split()
            if len(p) >= 2:
                pairs.setdefault(p[0].lower(), set()).add(p[1].lower())
        out = Path(args.out) if getattr(args, "out", None) else home_dir() / "menyoo"
        save_json(out / "anims.json", {k: sorted(v) for k, v in pairs.items()})
        return {"out": str(out / "anims.json"), "dicts": len(pairs), "clips": sum(len(v) for v in pairs.values()),
                "use": "set GTA_FORGE_ANIM_INDEX to this folder, then gtaforge anim --dict <name>"}
    name = {"anim": "PedAnimList.txt", "prop": "PropList.txt", "ped": "PedList.xml", "speech": "PedSpeechList.txt", "cutscene": "CutsceneLabels.txt"}.get(args.list or "anim")
    p = folder / name
    if not p.is_file():
        raise ForgeError(f"no {name} in {folder}", "gtaforge menyoo stats --folder ...")
    q = (args.query or "").lower()
    hits = [ln for ln in p.read_text(encoding="utf-8", errors="replace").splitlines() if q in ln.lower()]
    return {"list": name, "query": q, "count": len(hits), "lines": hits[:args.limit] if hasattr(args, "limit") else hits[:50]}