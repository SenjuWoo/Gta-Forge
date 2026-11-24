"""Routing and the knowledge base: which surface to use, which docs matter, what to avoid."""
from __future__ import annotations

import re

from .util import KNOWLEDGE_DIR, ForgeError, load_json


def docs() -> list[dict]:
    out = []
    for p in sorted(KNOWLEDGE_DIR.glob("*.md")):
        first = next((ln.lstrip("# ").strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()), p.stem)
        out.append({"name": p.name, "title": first})
    return out


def doc(name: str) -> str:
    p = KNOWLEDGE_DIR / (name if name.endswith(".md") else name + ".md")
    if not p.is_file():
        raise ForgeError(f"no knowledge doc '{name}'", "list them with: gtaforge knowledge")
    return p.read_text(encoding="utf-8")


def facts(key: str | None = None):
    data = load_json(KNOWLEDGE_DIR / "facts.json")["facts"]
    if key is None:
        return {k: {"tier": v["tier"]} for k, v in data.items()}
    hits = {k: v for k, v in data.items() if key.lower() in k.lower()}
    if not hits:
        raise ForgeError(f"no fact matching '{key}'", "list keys with: gtaforge facts")
    return hits


def plan(request: str) -> dict:
    data = load_json(KNOWLEDGE_DIR / "routes.json")
    text = " " + re.sub(r"[^a-z0-9+#.' ]+", " ", request.lower()) + " "
    scored = []
    for r in data["routes"]:
        score, hits = 0, []
        for kw in r["keywords"]:
            if f" {kw} " in text or (len(kw) > 4 and kw in text):
                score += 2 if " " in kw else 1
                hits.append(kw)
        if score:
            scored.append((score, r, hits))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return {"request": request, "route": None, "alternatives": [], "avoid": data.get("always_avoid", []),
                "hint": "no keyword matched; browse: gtaforge knowledge"}
    primary, alts = scored[0][1], [r for _s, r, _h in scored[1:3]]
    return {"request": request, "route": primary, "matched": scored[0][2], "alternatives": alts,
            "avoid": data.get("always_avoid", []) + primary.get("avoid", [])}