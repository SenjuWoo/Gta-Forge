"""Script projects: C++ (ScriptHookV SDK), C# (SHVDN), Lua (FiveM), Menyoo/XML data.

info  - detect the kind(s) in a folder; SDK / SHVDN references
check - static checks without compiling:
          C++   NS::NAME(...)          -> NAME is a native, NS is its namespace, argument count matches
          C#    Function.Call(Hash.NAME, ...) / Function.Call<T>((Hash)0x..., ...) -> exists, argument count
          XML   well-formed
          C++   ScriptHookV entry: scriptRegister in DllMain, no native calls from a raw CreateThread
lua   - luajit -bl syntax check of one file or folder
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .natives import _db, lookup
from .util import ForgeError, find_tool, read_text, run_proc

CPP_CALL = re.compile(r"\b([A-Z][A-Z0-9_]*)::(_?[A-Z0-9_]{3,}|_0x[0-9A-Fa-f]{6,16})\s*\(")
CS_CALL = re.compile(r"Function\.Call(?:<[^>()]*>)?\s*\(\s*(?:Hash\.(\w+)|\(Hash\)\s*(0x[0-9A-Fa-f]+)(?:UL|ul|L|l|u|U)?)")
SKIP_DIRS = {"build", "bin", "obj", ".git", ".vs", "out", "artifacts", "node_modules"}


def _files(folder: Path, exts: tuple[str, ...]) -> list[Path]:
    return [p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in exts
            and not any(part.lower() in SKIP_DIRS for part in p.relative_to(folder).parts[:-1])]


def detect(folder: Path) -> list[str]:
    kinds = []
    if (folder / "CMakeLists.txt").is_file() or _files(folder, (".vcxproj",)):
        kinds.append("cpp")
    if _files(folder, (".csproj",)):
        kinds.append("shvdn")
    if _files(folder, (".lua",)):
        kinds.append("lua")
    if _files(folder, (".xml",)):
        kinds.append("xml")
    if (folder / "menyooStuff").is_dir():
        kinds.append("menyoo")
    return kinds


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def count_args(text: str, open_paren: int) -> int | None:
    """Arguments of the call whose '(' is at open_paren (balanced brackets, strings skipped)."""
    depth, n, has_token, i = 0, 0, False, open_paren
    quote = None
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
            has_token = True
        elif c in "([{":
            depth += 1
            if depth > 1:
                has_token = True
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return n + (1 if has_token else 0)
        elif c == "," and depth == 1:
            n += 1
        elif not c.isspace() and depth >= 1:
            has_token = True
        i += 1
    return None


def _line(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def check_cpp(f: Path, text: str, errors: list, warnings: list) -> int:
    code = _strip_comments(text)
    calls = 0
    for m in CPP_CALL.finditer(code):
        ns, name = m.group(1), m.group(2)
        if ns in ("std", "GTA", "TEXT"):
            continue
        n = lookup(name) if not name.startswith("_0x") else lookup(name[1:])
        where = {"file": str(f), "line": _line(code, m.start())}
        if n is None:
            if ns.isupper() and len(ns) >= 3:
                errors.append({**where, "native": f"{ns}::{name}", "problem": "not a GTA V native (forge DB, 6,701 natives)"})
            continue
        calls += 1
        if n["name"] != name and not name.startswith("_0x"):
            warnings.append({**where, "native": name, "problem": f"old name; current is {n['ns']}::{n['name']}"})
        elif n["ns"] != ns:
            warnings.append({**where, "native": f"{ns}::{name}", "problem": f"namespace is {n['ns']} in the DB"})
        got = count_args(code, m.end() - 1)
        if got is not None and got != len(n["params"]):
            errors.append({**where, "native": n["name"], "problem": f"{got} argument(s), native takes {len(n['params'])}",
                           "signature": f"{n['returns']} {n['name']}(" + ", ".join(f"{p['type']} {p['name']}" for p in n["params"]) + ")"})
    if re.search(r"\bDllMain\b", code):
        if "scriptRegister" not in code:
            errors.append({"file": str(f), "problem": "DllMain without scriptRegister: natives only run in a script registered with ScriptHookV",
                           "fix": "scriptRegister(hModule, ScriptMain) on DLL_PROCESS_ATTACH, scriptUnregister(hModule) on detach"})
        if re.search(r"\bCreateThread\s*\(", code):
            warnings.append({"file": str(f), "problem": "CreateThread in an asi: never call natives from that thread (crash)",
                             "fix": "use scriptRegister / scriptRegisterAdditionalThread"})
    return calls


def check_cs(f: Path, text: str, errors: list, warnings: list) -> int:
    code = _strip_comments(text)
    calls = 0
    for m in CS_CALL.finditer(code):
        name, raw = m.group(1), m.group(2)
        n = lookup(name) if name else lookup(raw)
        where = {"file": str(f), "line": _line(code, m.start())}
        if n is None:
            errors.append({**where, "native": name or raw, "problem": "not a GTA V native (forge DB)"})
            continue
        calls += 1
        if name and n["name"] != name:
            warnings.append({**where, "native": name, "problem": f"old name; current is {n['name']} (SHVDN Hash enum may differ by version)"})
        paren = code.index("(", m.start() + len("Function.Call"))
        total = count_args(code, paren)
        if total is not None and total - 1 != len(n["params"]):
            errors.append({**where, "native": n["name"], "problem": f"{total - 1} argument(s), native takes {len(n['params'])}",
                           "signature": f"{n['returns']} {n['name']}(" + ", ".join(f"{p['type']} {p['name']}" for p in n["params"]) + ")"})
    return calls


def check_folder(folder: Path) -> dict:
    errors: list = []
    warnings: list = []
    files = 0
    calls = 0
    for f in _files(folder, (".cpp", ".cc", ".h", ".hpp", ".cs")):
        if f.name.lower() in ("natives.h", "nativecaller.h", "types.h", "enums.h", "main.h"):
            continue  # SDK / generated headers declare natives, they do not call them
        text = read_text(f)
        files += 1
        calls += (check_cs if f.suffix.lower() == ".cs" else check_cpp)(f, text, errors, warnings)
    for f in _files(folder, (".xml", ".meta", ".ymt.xml")):
        try:
            ET.parse(f)
        except ET.ParseError as e:
            errors.append({"file": str(f), "problem": f"XML: {e}"})
    return {"files": files, "native_calls": calls, "errors": errors, "warnings": warnings}


def run(args) -> dict:
    folder = Path(args.target or ".")
    if not folder.exists():
        raise ForgeError(f"no folder: {folder}", "pass a project folder")
    if args.action == "lua":
        exe = find_tool("luajit")
        if not exe:
            raise ForgeError("luajit not found", "install LuaJIT (or set LUAJIT to luajit/luac)")
        files = [folder] if folder.is_file() else _files(folder, (".lua",))
        out = []
        for f in files:
            flag = ["-p"] if Path(exe).stem.lower().startswith("luac") else ["-bl"]
            r = run_proc([exe, *flag, str(f)], timeout=60)
            out.append({"file": str(f), "code": r["code"], "error": r["stderr"].strip()[:300] if r["code"] else None})
        return {"checked": len(out), "failed": sum(1 for x in out if x["code"]), "files": out}
    if not folder.is_dir():
        raise ForgeError(f"not a folder: {folder}", "pass a project folder")
    kinds = detect(folder)
    if args.action == "info":
        return {"folder": str(folder), "kinds": kinds,
                "files": {k: len(_files(folder, (e,))) for k, e in (("cpp", ".cpp"), ("cs", ".cs"), ("lua", ".lua"), ("xml", ".xml"))},
                "sdk": find_tool("shv_sdk"), "shvdn": find_tool("shvdn_ref"), "natives_in_db": len(_db())}
    r = check_folder(folder)
    if "cpp" in kinds and not (find_tool("shv_sdk") or (folder / "inc").is_dir()):
        r["warnings"].append({"problem": "ScriptHookV SDK not found", "fix": "set SHV_SDK to the SDK folder (inc/, lib/)"})
    gaps = ["compile not run: gtaforge compile"] if {"cpp", "shvdn"} & set(kinds) else []
    return {"folder": str(folder), "kinds": kinds, **r, "gaps": gaps,
            "evidence": {"static": "failed" if r["errors"] else "passed", "compile": "not run", "load": "not run", "gameplay": "not run"}}
