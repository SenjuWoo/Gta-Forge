"""Read ScriptHookV / SHVDN / asi / game logs at once."""
from __future__ import annotations

import re
from pathlib import Path

from .util import read_text

LOG_GLOBS = ["ScriptHookV.log", "ScriptHookVDotNet.log", "ScriptHookVDotNet2.log", "ScriptHookVDotNet3.log",
             "*.asi.log", "asiloader.log", "GTAVLauncher.log", "logs/*.log"]
ERROR = re.compile(r"(?i)\b(error|exception|failed|fatal|crash|not found|unable)\b")


def run(game: Path, mod: str | None = None, limit: int = 200) -> dict:
    files: list[Path] = []
    for g in LOG_GLOBS:
        files += list(game.glob(g))
    out = []
    for f in sorted(set(files)):
        lines = read_text(f).splitlines()
        hits = [(i + 1, ln) for i, ln in enumerate(lines) if ERROR.search(ln) and (not mod or mod.lower() in ln.lower())]
        out.append({"file": str(f), "lines": len(lines), "errors": len(hits), "tail": hits[-limit:]})
    return {"game": str(game), "logs": out, "hint": "empty errors list means no matching line, not a clean run"}