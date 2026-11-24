"""Native DB search. Data: knowledge/natives.json (name, hash, return, params, since, note)."""
from __future__ import annotations

from .util import KNOWLEDGE_DIR, ForgeError, load_json, joaat


def _db() -> dict:
    return load_json(KNOWLEDGE_DIR / "natives.json")["natives"]


def search(query: str, limit: int = 25) -> dict:
    q = query.lower().strip()
    db = _db()
    hits = []
    for n in db:
        if q in n["name"].lower() or q in n.get("hash", "") or q in n.get("ns", "").lower():
            hits.append(n)
    return {"query": query, "count": len(hits), "total": len(db), "natives": hits[:limit],
            "source": "runtime.fivem.net/doc/natives.json subset (2026-11-24); hash = native hash",
            "hint": "gtaforge natives <name|hash|namespace>; full DB: https://docs.fivem.net/natives/"}


def joaat_of(name: str) -> str:
    return joaat(name)