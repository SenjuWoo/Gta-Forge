"""Install / remove a project's payload in the game for testing, with a receipt and backups.

- Writes only the resolved payload (build outputs, data), each file by copy to a temp name + rename.
- The first time a game file is replaced its original is backed up; later deploys keep that original,
  so `--remove` always restores the game as it was before the forge touched it.
- Every destination must stay inside the game folder.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from .package import resolve_payload
from .project import load_manifest
from .util import ForgeError, home_dir, load_json, save_json, sha256


def _receipt_path(name: str) -> Path:
    return home_dir() / "deploy" / f"{name}.json"


def _inside(root: Path, p: Path) -> bool:
    try:
        p.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _prune_empty_dirs(game: Path, dirs: list[Path]) -> None:
    """Remove folders the deploy created and left empty, walking up to (never including) the game root."""
    root = game.resolve()
    todo = set()
    for d in dirs:
        d = d.resolve()
        while d != root and _inside(root, d):
            todo.add(d)
            d = d.parent
    for d in sorted(todo, key=lambda p: len(p.parts), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()


def remove(m: dict, game: Path) -> dict:
    rp = _receipt_path(m["name"])
    if not rp.is_file():
        raise ForgeError("no deploy receipt; nothing was deployed by the forge", "gtaforge deploy first")
    rec = load_json(rp)
    restored, deleted, missing, changed = [], [], [], []
    for item in rec["files"]:
        dst = Path(item["dest"])
        if not _inside(game, dst):
            raise ForgeError(f"receipt points outside the game: {dst}", f"inspect {rp}")
        if not dst.is_file():
            missing.append(str(dst))
        elif item.get("sha256") and sha256(dst) != item["sha256"]:
            changed.append(str(dst))  # someone replaced it after us: leave it alone
            continue
        backup = Path(item["backup"]) if item.get("backup") else None
        if backup and backup.is_file():
            shutil.copy2(backup, dst)
            restored.append(str(dst))
        elif dst.is_file():
            dst.unlink()
            deleted.append(str(dst))
    _prune_empty_dirs(game, [Path(i["dest"]).parent for i in rec["files"]])
    rp.unlink()
    return {"removed": len(deleted), "restored": len(restored), "already_gone": missing, "changed_since_deploy": changed,
            "receipt": str(rp)}


def run(project: Path, game: Path, remove_: bool = False, dry_run: bool = False) -> dict:
    m = load_manifest(project)
    if remove_:
        return remove(m, game)
    if "lua" in m.get("kinds", []) and len(m["kinds"]) == 1:
        raise ForgeError("a FiveM Lua resource is not deployed into single-player GTA V", "copy the resource into your FiveM server")
    files = resolve_payload(project, m)
    if not files:
        raise ForgeError("payload is empty", "build first (gtaforge compile) or add payload rules to gtaforge.json")
    rp = _receipt_path(m["name"])
    old = load_json(rp) if rp.is_file() else {"files": []}
    originals = {i["dest"]: i.get("backup") for i in old.get("files", [])}
    backup_dir = home_dir() / "deploy" / "backups" / m["name"]
    plan = []
    for src, rel in files:
        dst = game / rel
        if not _inside(game, dst):
            raise ForgeError(f"payload escapes the game folder: {rel}", "fix the payload rule's 'to'")
        plan.append((src, dst, rel))
    if dry_run:
        return {"dry_run": True, "target": str(game), "files": [{"from": str(s), "to": str(d)} for s, d, _r in plan]}
    rec = {"name": m["name"], "version": m["version"], "game": str(game), "files": []}
    for src, dst, rel in plan:
        dst.parent.mkdir(parents=True, exist_ok=True)
        backup = originals.get(str(dst))
        if str(dst) not in originals and dst.is_file():
            b = backup_dir / rel
            b.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, b)
            backup = str(b)
        tmp = dst.with_name(dst.name + ".gtaforge_tmp")
        shutil.copy2(src, tmp)
        tmp.replace(dst)
        rec["files"].append({"src": str(src), "dest": str(dst), "backup": backup, "sha256": sha256(dst)})
    # files deployed last time but no longer in the payload: take them out (restore originals)
    stale = [i for i in old.get("files", []) if i["dest"] not in {r["dest"] for r in rec["files"]}]
    for i in stale:
        d = Path(i["dest"])
        if not _inside(game, d):
            continue
        if i.get("backup") and Path(i["backup"]).is_file():
            shutil.copy2(i["backup"], d)
        elif d.is_file():
            d.unlink()
    save_json(rp, rec)
    return {"deployed": len(rec["files"]), "target": str(game), "receipt": str(rp), "stale_removed": len(stale),
            "files": [i["dest"] for i in rec["files"]],
            "note": "story mode only; launch with -nobattleye (Enhanced: args.txt or PlayGTAV.exe -nobattleye)"}
