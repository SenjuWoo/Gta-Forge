"""Binding-table coverage: does every content key a mod needs resolve to an asset that exists in the game?

Format (GTA 6.5 Leonida Living World uses it; any mod may):
  keys file   {"keys": {"<key>": {"module": "casino", "type": "anim|model|prop|ped|vehicle|texture|interior|audio|any",
                                   "required": true, "note": "..."}}}
  table file  {"game": "gta5", "bindings": {"<key>": "<asset name>"
                                                 | {"dict": "<anim dict>", "clip": "<clip>"}
                                                 | {"model": "<model>"} | {"name": "<asset>", "type": "..."}
                                                 | null   (known missing: the feature degrades)}}
Checks: key bound (or explicitly null), asset present in the installed game's asset index (gtaforge index
build), anim clip present in the anim index when one is configured. Coverage is reported per module.
"""
from __future__ import annotations

from pathlib import Path

from .util import ForgeError, load_json

MODEL_EXT = (".ydr", ".yft", ".ydd")
TYPE_EXT = {"anim": (".ycd",), "model": MODEL_EXT, "prop": MODEL_EXT, "ped": (".yft", ".ydd", ".ymt"),
            "vehicle": (".yft",), "texture": (".ytd",), "interior": (".ytyp", ".ymap"), "audio": (".awc",), "map": (".ymap",)}


def _asset(binding) -> tuple[str | None, str | None, str | None]:
    """(asset name, clip, explicit type) from a binding value."""
    if binding is None:
        return None, None, None
    if isinstance(binding, str):
        return binding, None, None
    if isinstance(binding, dict):
        if binding.get("dict"):
            return binding["dict"], binding.get("clip"), "anim"
        for k in ("model", "name", "asset", "ped", "prop", "vehicle", "texture"):
            if binding.get(k):
                return binding[k], None, binding.get("type") or (k if k in TYPE_EXT else None)
    raise ForgeError(f"unreadable binding value: {binding!r}", 'use "name", {"dict","clip"}, {"model"} or null')


def check(keys_file: Path, table_file: Path, game: Path | None = None, use_index: bool = True) -> tuple[dict, int]:
    for p in (keys_file, table_file):
        if not p.is_file():
            raise ForgeError(f"no file: {p}", "pass the binding keys file and the game's table")
    try:
        keys = load_json(keys_file).get("keys", {})
        table = load_json(table_file)
    except (ValueError, AttributeError) as e:
        raise ForgeError(f"binding file is not valid JSON: {e}", "fix the file") from None
    bindings = table.get("bindings", {})
    if not isinstance(keys, dict) or not isinstance(bindings, dict):
        raise ForgeError("keys/bindings must be JSON objects", "see gtaforge knowledge bindings")
    exists = None
    if use_index:
        try:
            from .index import current_index, exists as idx_exists
            current_index(game)
            exists = idx_exists
        except ForgeError:
            exists = None
    clip_lookup = None
    try:
        from .anims import index_dir, _load_all
        if index_dir().is_dir():
            anim_data = _load_all(index_dir())
            clip_lookup = lambda d, c: c.lower() in {x.lower() for x in anim_data.get(d.lower(), anim_data.get(d, []))}
    except ForgeError:
        clip_lookup = None
    rows, modules = [], {}
    problems = 0
    for key, spec in sorted(keys.items()):
        spec = spec or {}
        mod = spec.get("module", "other")
        m = modules.setdefault(mod, {"keys": 0, "bound": 0, "verified": 0, "missing_required": 0})
        m["keys"] += 1
        row = {"key": key, "module": mod, "type": spec.get("type"), "required": bool(spec.get("required"))}
        if key not in bindings:
            row["status"] = "unbound"
            if row["required"]:
                m["missing_required"] += 1
                problems += 1
            rows.append(row)
            continue
        name, clip, btype = _asset(bindings[key])
        if name is None:
            row["status"] = "declared-missing"
            if row["required"]:
                m["missing_required"] += 1
                problems += 1
            rows.append(row)
            continue
        m["bound"] += 1
        row.update(asset=name, clip=clip)
        typ = btype or spec.get("type") or "any"
        if exists is None:
            row["status"] = "bound (not verified: no asset index)"
        else:
            hits = exists(name, game)
            exts = TYPE_EXT.get(typ)
            if exts:
                hits = [h for h in hits if h["path"].lower().endswith(exts)]
            if not hits:
                row["status"] = "asset not in game"
                problems += 1
            else:
                row["status"] = "verified"
                row["where"] = hits[0]["path"]
                m["verified"] += 1
                if clip and clip_lookup is not None and not clip_lookup(name, clip):
                    row["status"] = "clip not in anim index"
                    m["verified"] -= 1
                    problems += 1
        rows.append(row)
    extra = sorted(set(bindings) - set(keys))
    for mod, m in modules.items():
        m["coverage"] = round(m["bound"] / m["keys"], 3) if m["keys"] else 1.0
    total = len(keys)
    report = {"keys_file": str(keys_file), "table": str(table_file), "game": table.get("game"), "keys": total,
              "bound": sum(m["bound"] for m in modules.values()), "verified": sum(m["verified"] for m in modules.values()),
              "index_used": exists is not None, "modules": modules, "unknown_keys_in_table": extra,
              "rows": rows, "problems": problems}
    return report, (1 if problems else 0)
