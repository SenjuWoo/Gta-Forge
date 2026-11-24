"""Animation dictionary / clip lookup from the GTA V anim index (data/gta5/anim_index or a Menyoo list).

The forge ships no anim data of its own. --index points at a folder of
{dict: [clips]} JSON files (e.g. the GTA 6.5 project's data/gta5/anim_index,
or gtaforge menyoo index output). Without it, the command reports what to build.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .util import ForgeError, home_dir, load_json


def index_dir(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit)
    env = os.environ.get("GTA_FORGE_ANIM_INDEX")
    if env:
        return Path(env)
    return home_dir() / "anim_index"


def _load_all(folder: Path) -> dict:
    out = {}
    for p in sorted(folder.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            out.update({k: v for k, v in data.items() if isinstance(v, list)})
    return out


def lookup(dict_name: str | None = None, clip: str | None = None, pattern: str | None = None,
           game: str | None = None, limit: int = 30) -> dict:
    folder = index_dir()
    if not folder.is_dir():
        raise ForgeError(f"anim index not found: {folder}",
                         "build one: gtaforge menyoo index --folder <menyooStuff>, or set GTA_FORGE_ANIM_INDEX")
    data = _load_all(folder)
    if dict_name:
        d = data.get(dict_name.lower(), data.get(dict_name))
        if d is None:
            near = [k for k in data if dict_name.lower() in k.lower()][:10]
            return {"dict": dict_name, "found": False, "near": near, "total_dicts": len(data)}
        clips = [c for c in d if not clip or clip.lower() in c.lower()]
        return {"dict": dict_name, "found": True, "clips": clips[:limit], "clip_count": len(d)}
    if pattern:
        hits = {k: v[:12] for k, v in data.items() if pattern.lower() in k.lower()}
        return {"pattern": pattern, "dicts": len(hits), "matches": dict(list(hits.items())[:limit])}
    raise ForgeError("pass --dict <name> [--clip <part>] or --pattern <part>", "gtaforge anim --dict mini@prostitutes@sexnorm_veh")