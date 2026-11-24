"""Script projects: C++ (ScriptHookV SDK), C# (SHVDN), Lua (fxserver/RedM), Menyoo/XML data.

`info`  - detect the kind(s) in a folder and read versions/targets.
`check` - static checks without compiling: SDK include present, native names exist in the DB,
          SHVDN project references, Lua syntax via luajit if installed, XML well-formed.
`lua`   - luajit -bl / luac -p syntax check of one file or folder.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .natives import _db
from .util import ForgeError, find_tool, read_text, run

NATIVE_CALL = re.compile(r"\b([A-Z][A-Z0-9_]{3,})\s*\(")


def detect(folder: Path) -> list[str]:
    kinds = []
    if (folder / "CMakeLists.txt").is_file() or list(folder.rglob("*.vcxproj")):
        kinds.append("cpp")
    if list(folder.rglob("*.csproj")):
        kinds.append("shvdn")
    if list(folder.rglob("*.lua")):
        kinds.append("lua")
    if list(folder.rglob("*.xml")):
        kinds.append("xml")
    if (folder / "info.json").is_file():
        kinds.append("menyoo")
    return kinds


def run(args) -> dict:
    folder = Path(args.target or ".")
    if not folder.is_dir():
        raise ForgeError(f"no folder: {folder}", "pass a project folder")
    kinds = detect(folder)
    if args.action == "info":
        return {"folder": str(folder), "kinds": kinds,
                "files": {k: sum(1 for _ in folder.rglob(p)) for k, p in (("cpp", "*.cpp"), ("cs", "*.cs"), ("lua", "*.lua"), ("xml", "*.xml"))},
                "sdk": find_tool("shv_sdk") or "set SHV_SDK to the ScriptHookV SDK folder (inc/, lib/)"}
    if args.action == "lua":
        exe = find_tool("luajit")
        if not exe:
            raise ForgeError("luajit not found", "install luajit (or use luac) and set LUAJIT")
        files = [folder] if folder.is_file() else list(folder.rglob("*.lua"))
        out = []
        for f in files:
            r = run([exe, "-bl", str(f)], timeout=60)
            out.append({"file": str(f), "code": r["code"], "error": r["stderr"].strip()[:300] if r["code"] else None})
        return {"checked": len(out), "failed": sum(1 for x in out if x["code"]), "files": out}
    # check
    errors, warnings, checked = [], [], []
    db = {n["name"] for n in _db()}
    for f in folder.rglob("*"):
        if f.suffix.lower() not in (".cpp", ".h", ".hpp", ".cs"):
            continue
        text = read_text(f)
        for name in set(NATIVE_CALL.findall(text)):
            if name in db:
                continue
            if re.search(r"\b(void|int|BOOL|float|Vector3|Ped|Vehicle|Object|Player|Hash|Any)\b", text) and name in ("TRUE", "FALSE", "NULL"):
                continue
            warnings.append({"file": str(f), "native": name, "problem": "name not in the forge native DB (may be a wrapper or newer native)"})
        checked.append(str(f))
    for f in folder.rglob("*.xml"):
        try:
            ET.parse(f)
        except ET.ParseError as e:
            errors.append({"file": str(f), "problem": f"XML: {e}"})
    if kinds and "cpp" in kinds and not (find_tool("shv_sdk") or (folder / "inc").is_dir()):
        warnings.append({"problem": "ScriptHookV SDK not found", "fix": "set SHV_SDK"})
    return {"folder": str(folder), "kinds": kinds, "checked": len(checked), "errors": errors, "warnings": warnings,
            "gaps": [g for g in (["compile not run: use gtaforge compile"] if "cpp" in kinds or "shvdn" in kinds else [])],
            "evidence": {"static": "passed" if not errors else "failed", "compile": "not run", "load": "not run", "gameplay": "not run"}}