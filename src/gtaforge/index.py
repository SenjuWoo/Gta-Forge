"""Asset index of the installed game: every entry of every archive (nested), so a name is confirmed, not guessed.

build -> ragekit `rpf ls -r --nested --tsv` over the game's archives (or the python reader for OPEN ones)
         -> <home>/index/<edition>-<version>.tsv.gz  (archive-relative path, kind, size)
find  -> exact asset name (stem, any extension) or substring; tells which archive holds it

Asset types worth knowing: .ycd clip dictionary (= anim dict name), .ydr/.ydd/.yft models,
.ytd textures, .ymap/.ytyp placements/archetypes, .awc audio, .ysc scripts, .gxt2 text.
"""
from __future__ import annotations

import gzip
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

from .util import ForgeError, home_dir, save_json

KINDS = {".ycd": "anim_dict", ".ydr": "model", ".ydd": "model_dict", ".yft": "fragment", ".ytd": "texture_dict",
         ".ymap": "map", ".ytyp": "archetypes", ".ybn": "collision", ".ynv": "navmesh", ".awc": "audio",
         ".ysc": "script", ".gxt2": "text", ".ypt": "particles", ".ymt": "metadata", ".meta": "metadata", ".rpf": "archive"}


def index_dir() -> Path:
    env = os.environ.get("GTA_FORGE_INDEX")
    return Path(env) if env else home_dir() / "index"


def archives(game: Path) -> list[Path]:
    out = sorted(game.glob("*.rpf"))
    upd = game / "update"
    out += sorted(upd.glob("*.rpf")) if upd.is_dir() else []
    for sub in ("update/x64/dlcpacks", "x64/dlcpacks", "mods/update/x64/dlcpacks"):
        d = game / sub
        if d.is_dir():
            out += sorted(d.glob("*/*.rpf"))
    return out


def index_file(game: Path) -> Path:
    from .game import edition
    ed = edition(game)
    tag = f"{ed.get('edition') or 'unknown'}-{ed.get('file_version') or 'unknown'}"
    return index_dir() / f"{tag}.tsv.gz"


def _list_one(arc: Path, game: Path) -> tuple[str, list[dict], str | None]:
    from .rpf import list_entries
    rel = arc.relative_to(game).as_posix()
    try:
        _engine, items, _head = list_entries(arc, nested=True, game=game)
        return rel, items, None
    except ForgeError as e:
        return rel, [], f"{e} ({e.fix})"


def build(game: Path, workers: int = 4, limit: int | None = None) -> dict:
    t0 = time.time()
    arcs = archives(game)[:limit] if limit else archives(game)
    if not arcs:
        raise ForgeError(f"no .rpf archives under {game}", "pass the game folder")
    rows: list[str] = []
    errors = []
    counts: dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        for rel, items, err in ex.map(lambda a: _list_one(a, game), arcs):
            if err:
                errors.append({"archive": rel, "error": err})
                continue
            for i in items:
                if i["kind"] == "dir":
                    continue
                path = f"{rel}/{i['path']}"
                rows.append(f"{path}\t{i['kind']}\t{i.get('size') or 0}")
                k = KINDS.get(Path(i["path"]).suffix.lower(), "other")
                counts[k] = counts.get(k, 0) + 1
    if not rows:
        raise ForgeError("index is empty: no archive could be listed", errors[0]["error"] if errors else "gtaforge rpf doctor")
    out = index_file(game)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(rows) + "\n")
    tmp.replace(out)
    summary = {"index": str(out), "game": str(game), "archives": len(arcs), "listed": len(arcs) - len(errors),
               "entries": len(rows), "by_kind": dict(sorted(counts.items())), "errors": errors[:20],
               "seconds": round(time.time() - t0, 1), "built": time.strftime("%Y-%m-%d %H:%M:%S")}
    save_json(out.with_suffix("").with_suffix(".json"), summary)
    _load.cache_clear()
    return summary


@lru_cache(maxsize=4)
def _load(path: str) -> tuple[list[tuple[str, str, int]], dict[str, list[int]]]:
    rows = []
    stems: dict[str, list[int]] = {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            p, k, s = line.rstrip("\n").split("\t")
            idx = len(rows)
            rows.append((p, k, int(s) if s.isdigit() else 0))
            name = p.rsplit("/", 1)[-1].lower()
            stems.setdefault(name.rsplit(".", 1)[0], []).append(idx)
            stems.setdefault(name, []).append(idx)
    return rows, stems


def current_index(game: Path | None = None) -> Path:
    if game is not None:
        p = index_file(game)
        if p.is_file():
            return p
    cands = sorted(index_dir().glob("*.tsv.gz"), key=lambda p: p.stat().st_mtime, reverse=True) if index_dir().is_dir() else []
    if not cands:
        raise ForgeError("no asset index yet", "gtaforge index build  (needs ragekit + gtaforge rpf keys; a few minutes)")
    return cands[0]


def exists(name: str, game: Path | None = None, ext: str | None = None) -> list[dict]:
    rows, stems = _load(str(current_index(game)))
    hits = [rows[i] for i in stems.get(name.lower(), [])]
    if ext:
        hits = [h for h in hits if h[0].lower().endswith(ext.lower())]
    return [{"path": p, "kind": KINDS.get(Path(p).suffix.lower(), "other"), "size": s} for p, _k, s in hits]


def find_batch(names: list[str], game: Path | None = None, ext: str | None = None, where: int = 3) -> dict:
    """Many exact lookups with one index load. `g9ec` marks names that also exist in an Enhanced-generation
    (`*_g9ec`) pack, the higher-resolution copies Enhanced added."""
    idx = current_index(game)
    items, missing = [], []
    seen = set()
    for raw in names:
        name = raw.strip()
        if not name or name.startswith("#") or name.lower() in seen:
            continue
        seen.add(name.lower())
        hits = exists(name, game, ext)
        row = {"name": name, "found": bool(hits), "count": len(hits), "where": [h["path"] for h in hits[:where]],
               "g9ec": any("g9ec" in h["path"].lower() for h in hits)}
        if hits:
            row["kinds"] = sorted({h["kind"] for h in hits})
        else:
            missing.append(name)
        items.append(row)
    return {"index": str(idx), "names": len(items), "found": len(items) - len(missing), "missing_count": len(missing),
            "missing": missing, "items": items}


def find(query: str, game: Path | None = None, limit: int = 50, ext: str | None = None) -> dict:
    if not query.strip():
        raise ForgeError("empty query", "gtaforge find <asset name or part>")
    idx = current_index(game)
    rows, _stems = _load(str(idx))
    exact = exists(query, game, ext)
    q = query.lower()
    partial = [r for r in rows if q in r[0].rsplit("/", 1)[-1].lower() and (not ext or r[0].lower().endswith(ext.lower()))]
    meta = idx.with_suffix("").with_suffix(".json")
    return {"query": query, "index": str(idx), "found": bool(exact), "exact": exact[:limit],
            "partial_count": len(partial),
            "partial": [{"path": p, "kind": KINDS.get(Path(p).suffix.lower(), "other"), "size": s} for p, _k, s in partial[:limit]],
            "index_built": json.loads(meta.read_text(encoding="utf-8")).get("built") if meta.is_file() else None}
