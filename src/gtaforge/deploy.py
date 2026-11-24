"""Install / remove a project in the game for testing, with a receipt and backups.

Writes by copy + rename (never through a mod manager's hard links). Default target:
  cpp/xml/menyoo -> game root (asi, data) ; shvdn/lua -> game/scripts/<name>
"""
from __future__ import annotations

import shutil
from pathlib import Path

from .package import runtime_files
from .util import ForgeError, home_dir, load_json, save_json


def _target(game: Path, kind: str, name: str) -> Path:
    return game / "scripts" / name if kind in ("shvdn", "lua") else game


def run(project: Path, game: Path, remove: bool = False) -> dict:
    m = load_json(project / "gtaforge.json")
    dest = _target(game, m["kinds"][0] if m["kinds"] else "cpp", m["name"])
    receipt_path = home_dir() / "deploy" / f"{m['name']}.json"
    if remove:
        rec = load_json(receipt_path) if receipt_path.is_file() else None
        if not rec:
            raise ForgeError("no deploy receipt; nothing was deployed by the forge", "gtaforge deploy first")
        undone, missing = [], []
        for item in rec["files"]:
            dst = Path(item["dest"])
            if dst.is_file():
                backup = Path(item["backup"]) if item.get("backup") else None
                if backup and backup.is_file():
                    shutil.copy2(backup, dst)
                    undone.append(str(dst))
                else:
                    dst.unlink()
                    undone.append(str(dst))
            else:
                missing.append(str(dst))
        receipt_path.unlink(missing_ok=True)
        return {"removed": len(undone), "already_gone": missing, "receipt": str(receipt_path)}
    files = runtime_files(project)
    if not files:
        raise ForgeError("nothing to deploy", "add the payload first")
    backup_dir = home_dir() / "deploy" / "backups" / m["name"]
    rec = {"name": m["name"], "version": m["version"], "files": []}
    for p in files:
        rel = p.relative_to(project)
        dst = dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / rel
        if dst.is_file():
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, backup)
        tmp = dst.with_suffix(dst.suffix + ".gtaforge_tmp")
        shutil.copy2(p, tmp)
        tmp.replace(dst)
        rec["files"].append({"src": str(p), "dest": str(dst), "backup": str(backup) if backup.is_file() else None})
    save_json(receipt_path, rec)
    return {"deployed": len(rec["files"]), "target": str(dest), "receipt": str(receipt_path),
            "note": "launch the game with -nobattleye; never in GTA Online"}