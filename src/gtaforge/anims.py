"""Animation dictionaries and clips.

lookup  - dict / clip lookup in an anim index: a folder of {dict: [clips]} JSON files
          (GTA_FORGE_ANIM_INDEX, a Menyoo index from `gtaforge menyoo index`, or the game clip index below)
clips   - clip names read from the installed game: the dict's .ycd is pulled out of its archive with
          ragekit (`rpf cat`) and listed with `ragekit info -v`; cached per game version
build   - the same for many dicts at once -> <home>/anim_index_game/<edition>-<version>.json, which
          `lookup` and `bindings` then use: clip names confirmed in the installed build, not a community list
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .util import ForgeError, find_tool, home_dir, load_json, run_proc, save_json

CLIP_LINE = re.compile(r"^\s+(?:pack:/)?([^\s:][^:]*?)\.clip:", re.M)


def game_index_dir() -> Path:
    return home_dir() / "anim_index_game"


def index_dir(explicit: str | None = None) -> Path:
    """Explicit > GTA_FORGE_ANIM_INDEX > game clip index (if built) > <home>/anim_index."""
    if explicit:
        return Path(explicit)
    env = os.environ.get("GTA_FORGE_ANIM_INDEX")
    if env:
        return Path(env)
    g = game_index_dir()
    if g.is_dir() and any(g.glob("*.json")):
        return g
    return home_dir() / "anim_index"


def _load_all(folder: Path) -> dict:
    out = {}
    for p in sorted(folder.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            out.update({k.lower(): v for k, v in data.items() if isinstance(v, list)})
    return out


def lookup(dict_name: str | None = None, clip: str | None = None, pattern: str | None = None,
           game: str | None = None, limit: int = 30) -> dict:
    folder = index_dir()
    if not folder.is_dir():
        raise ForgeError(f"anim index not found: {folder}",
                         "gtaforge anim build --batch <dicts.txt> (clips from the game), or gtaforge menyoo index --folder <menyooStuff>")
    data = _load_all(folder)
    if dict_name:
        d = data.get(dict_name.lower())
        if d is None:
            near = [k for k in data if dict_name.lower() in k][:10]
            return {"dict": dict_name, "found": False, "near": near, "total_dicts": len(data), "index": str(folder)}
        clips = [c for c in d if not clip or clip.lower() in c.lower()]
        return {"dict": dict_name, "found": True, "clips": clips[:limit], "clip_count": len(d), "index": str(folder),
                "clip_match": (clip.lower() in {c.lower() for c in d}) if clip else None}
    if pattern:
        hits = {k: v[:12] for k, v in data.items() if pattern.lower() in k}
        return {"pattern": pattern, "dicts": len(hits), "matches": dict(list(hits.items())[:limit]), "index": str(folder)}
    raise ForgeError("pass --dict <name> [--clip <part>] or --pattern <part>", "gtaforge anim --dict mini@strip_club@idles@stripper")


def _cache_dir(game: Path | None) -> Path:
    from .index import current_index
    return home_dir() / "clips" / current_index(game).name.replace(".tsv.gz", "")


def parse_info(text: str) -> list[str]:
    return sorted({m.group(1) for m in CLIP_LINE.finditer(text)})


def clips(dict_name: str, game: Path | None = None, refresh: bool = False) -> dict:
    """Clip names of one dict, read from the installed game (cached)."""
    from .index import exists
    from .rpf import _edition_flag
    cache = _cache_dir(game) / f"{dict_name.lower()}.json"
    if cache.is_file() and not refresh:
        return {**load_json(cache), "cached": True}
    rk = find_tool("ragekit")
    if not rk:
        raise ForgeError("ragekit not found", "build vendor/ragekit-main or set RAGEKIT_CLI")
    hits = exists(dict_name, game, ".ycd")
    if not hits:
        raise ForgeError(f"no clip dictionary '{dict_name}' in the asset index", "check the name: gtaforge find <part> --ext .ycd")
    if game is None:
        from .game import require_game
        game = require_game(None)
    where = hits[0]["path"]
    parts = where.split("/")
    cut = next(i for i, p in enumerate(parts) if p.lower().endswith(".rpf")) + 1
    archive, inner = game.joinpath(*parts[:cut]), "/".join(parts[cut:])
    with tempfile.TemporaryDirectory(prefix="gtaforge_ycd_") as tmp:
        ycd = Path(tmp) / "d.ycd"
        r = run_proc([rk, "rpf", "cat", str(archive), inner, str(ycd), _edition_flag(archive, game)], timeout=300)
        if r["code"] or not ycd.is_file():
            raise ForgeError(f"ragekit could not extract {where}: {(r['stderr'] or r['stdout']).strip()[-200:]}", "gtaforge rpf keys")
        info = run_proc([rk, "info", str(ycd), "-v"], timeout=300)
    names = parse_info(info["stdout"])
    m = re.search(r"clip dictionary: (\d+) clips", info["stdout"])
    declared = int(m.group(1)) if m else None
    res = {"dict": dict_name, "where": where, "clips": names, "clip_count": len(names), "declared": declared,
           "complete": declared is None or declared == len(names)}
    save_json(cache, res)
    return res


def build(names: list[str], game: Path | None = None, workers: int = 8) -> dict:
    """Clip lists for many dicts -> the game clip index used by lookup/bindings."""
    from .index import current_index
    names = sorted({n.strip().lower() for n in names if n.strip() and not n.startswith("#")})
    if not names:
        raise ForgeError("no dict names", "one anim dict per line")
    out, missing, failed = {}, [], []

    def one(n):
        try:
            return n, clips(n, game), None
        except ForgeError as e:
            return n, None, str(e)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        for n, res, err in ex.map(one, names):
            if res:
                out[n] = res["clips"]
            elif err and "no clip dictionary" in err:
                missing.append(n)
            else:
                failed.append({"dict": n, "error": err})
    dest = game_index_dir() / (current_index(game).name.replace(".tsv.gz", "") + ".json")
    merged = load_json(dest) if dest.is_file() else {}
    merged.update(out)
    save_json(dest, dict(sorted(merged.items())))
    return {"index": str(dest), "requested": len(names), "read": len(out), "clips": sum(len(v) for v in out.values()),
            "not_in_game": missing[:200], "failed": failed[:50], "total_dicts_in_index": len(merged)}
