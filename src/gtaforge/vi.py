"""GTA VI readiness (no game needed).

status      - platform + file-tool watch from knowledge/vi.json
tools       - the RPF9/TTPF index (vendor/awesome-gta6-reverse-engineering-main/README.md) as JSON links
build-6to5m - cargo build --release in vendor/6to5m-main (Rust), report the binary path
"""
from __future__ import annotations

import re
from pathlib import Path

from .util import ForgeError, KNOWLEDGE_DIR, find_tool, load_json, run

VENDOR = Path(__file__).resolve().parents[2] / "vendor"


def run(args) -> dict:
    facts = load_json(KNOWLEDGE_DIR / "vi.json")
    if args.action == "status":
        return {"checked": facts["checked"], "platform": facts["platform"], "file_tools": facts["file_tools"],
                "note": facts["note"]}
    if args.action == "tools":
        md = VENDOR / "awesome-gta6-reverse-engineering-main" / "README.md"
        if not md.is_file():
            raise ForgeError("index not vendored", "clone Ahmet-Dedeler/awesome-gta6-reverse-engineering into vendor/")
        links = sorted(set(re.findall(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", md.read_text(encoding="utf-8", errors="replace"))))
        return {"index": str(md), "projects": len(links), "links": links}
    if args.action == "build-6to5m":
        cargo = find_tool("cargo")
        src = VENDOR / "6to5m-main"
        if not cargo:
            raise ForgeError("cargo not found", "install Rust (rustup) then retry")
        if not (src / "Cargo.toml").is_file():
            raise ForgeError("6to5m source not vendored", "clone DesignWithTommy/6to5m into vendor/6to5m-main")
        r = run([cargo, "build", "--release", "--offline"], cwd=src, timeout=1800)
        exe = src / "target/release/6ixpack.exe"
        return {"engine": "6to5m", **r, "binary": str(exe) if exe.is_file() else None,
                "evidence": {"compile": "passed" if r["code"] == 0 and exe.is_file() else "failed"}}
    raise ForgeError("unknown action", "status | tools | build-6to5m")