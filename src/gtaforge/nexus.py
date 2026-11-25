"""Nexus page kit: description skeleton, changelog block, BBCode. No upload."""
from __future__ import annotations

from pathlib import Path

from .project import load_manifest
from .util import ForgeError


def run(project: Path) -> dict:
    m = load_manifest(project)
    if not (project / "CHANGELOG.md").is_file():
        raise ForgeError("no CHANGELOG.md", "add one (Keep a Changelog)")
    text = (project / "CHANGELOG.md").read_text(encoding="utf-8")
    top = text.split("## ", 1)[1].split("\n## ", 1)[0] if "## " in text else text
    return {"name": m["name"], "version": m["version"],
            "description": f"[h1]{m['name']}[/h1]\n\nWhat it does, which game edition, requirements (ScriptHookV etc.), install, uninstall.",
            "changelog_bbcode": "[b]" + top.splitlines()[0].strip() + "[/b]\n" + "\n".join(top.splitlines()[1:]),
            "tags": ["GTA V", m.get("game", "auto")], "note": "public text: no personal names or machine paths"}