"""GTA VI readiness and the day-one kit. Nothing here needs a GTA VI build to run; all of it is
tested on synthetic RPF9 files and on the installed GTA V as a known-format control.

status      - platform + file-tool watch (knowledge/vi.json)
tools       - the RPF9/TTPF community index (vendor/awesome-gta6-reverse-engineering-main) as links
build-6to5m - cargo build --release of vendor/6to5m-main; reports the binary
probe       - census of any game folder or dump: executables (version, sha256), archive formats by magic
              (RPF7/8/9), RPF9 header fields + nested archive count, other RAGE signatures; writes a report
names       - name recovery: joaat every candidate name (wordlist, Menyoo lists, GTA V index, generated
              variants) and match against a hash list (hex/decimal text, or raw u32 tables)
checklist   - the 12 first checks (GTA 6.5 docs/GTA6-TOOLING-WATCH.md section 4), each run where a tool can
extract     - 6ixpack <file> [outdir] (list-only with --list)
"""
from __future__ import annotations

import os
import re
import struct
import time
from pathlib import Path

from . import rpf9
from .util import ForgeError, KNOWLEDGE_DIR, file_version, find_tool, home_dir, joaat, load_json, run_proc, save_json, sha256

VENDOR = Path(__file__).resolve().parents[2] / "vendor"
EXE_HINTS = ("gta6", "gtavi", "gta_vi", "grand theft auto vi", "victory", "leonida")
CUT_CONTENT_TERMS = ("casino", "blackjack", "roulette", "slot", "poker", "darts", "bowling", "tennis", "prostitute",
                     "hooker", "stripclub", "strip_club", "nude", "naked", "sex", "lapdance", "yoga", "golf", "arcade")


def _status() -> dict:
    facts = load_json(KNOWLEDGE_DIR / "vi.json")
    return {"checked": facts["checked"], "platform": facts["platform"], "file_tools": facts["file_tools"], "note": facts["note"],
            "local_tools": {"6ixpack": find_tool("6to5m"), "cargo": find_tool("cargo")}}


def _walk(root: Path, max_files: int):
    n = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d.lower() not in ("$recycle.bin",)]
        for fn in filenames:
            yield Path(dirpath) / fn
            n += 1
            if n >= max_files:
                return


def probe(folder: Path, out: Path | None = None, max_files: int = 200_000, hash_exes: bool = True, nested: bool = True) -> dict:
    """What a folder holds, by content signature, not by extension. Read-only."""
    if not folder.exists():
        raise ForgeError(f"no such folder: {folder}", "pass the game folder or a dump")
    files = [folder] if folder.is_file() else list(_walk(folder, max_files))
    census: dict[str, dict] = {}
    archives, exes, unknown_ext = [], [], {}
    total = 0
    for f in files:
        try:
            size = f.stat().st_size
            with open(f, "rb") as h:
                head = h.read(16)
        except OSError:
            continue
        total += size
        kind = rpf9.sniff(head)
        c = census.setdefault(kind, {"files": 0, "bytes": 0, "description": rpf9.describe(kind)})
        c["files"] += 1
        c["bytes"] += size
        rel = str(f.relative_to(folder)) if f != folder else f.name
        if kind == "unknown":
            ext = f.suffix.lower() or "(none)"
            unknown_ext[ext] = unknown_ext.get(ext, 0) + 1
        if kind in ("rpf7", "rpf8", "rpf9", "rpf6", "rpf7-be"):
            a = {"path": rel, "format": kind, "bytes": size}
            if kind == "rpf9":
                try:
                    r = rpf9.read(f, nested=nested)
                    a.update(header=r["header"], nested=r["nested"])
                except ForgeError as e:
                    a["error"] = str(e)
            elif kind == "rpf7":
                count, names_len, enc = struct.unpack_from("<III", head, 4)
                from .rpf7 import encryption_name
                a.update(entries=count, names_length=names_len, encryption=encryption_name(enc))
            archives.append(a)
        if kind == "pe" and f.suffix.lower() == ".exe":
            e = {"path": rel, "bytes": size, "file_version": file_version(f)}
            if hash_exes and size < 2_000_000_000:
                e["sha256"] = sha256(f)
            e["looks_like_title"] = any(t in f.name.lower() for t in EXE_HINTS) or size > 40_000_000
            exes.append(e)
    report = {"folder": str(folder), "files": len(files), "bytes": total, "truncated": len(files) >= max_files,
              "census": dict(sorted(census.items(), key=lambda kv: -kv[1]["bytes"])),
              "archives": {"count": len(archives), "by_format": _count(a["format"] for a in archives), "items": archives[:500]},
              "executables": exes, "unknown_extensions": dict(sorted(unknown_ext.items(), key=lambda kv: -kv[1])[:30]),
              "verdict": _verdict(census, archives),
              "probed": time.strftime("%Y-%m-%d %H:%M:%S")}
    out = out or (home_dir() / "vi" / f"probe-{_slug(folder)}.json")
    save_json(out, report)
    report["report"] = str(out)
    return report


def _count(items) -> dict:
    out: dict = {}
    for i in items:
        out[i] = out.get(i, 0) + 1
    return out


def _slug(p: Path) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", p.name or "root").strip("-")[:60] or "root"


def _verdict(census: dict, archives: list) -> str:
    fmts = {a["format"] for a in archives}
    if "rpf9" in fmts:
        return "GTA VI archive format (RPF9) present: run vi extract / 6ixpack; tables need 6to5m's decoder"
    if "rpf8" in fmts:
        return "RDR2-style RPF8 archives"
    if "rpf7" in fmts:
        return "GTA V RPF7 archives (use gtaforge rpf / index)"
    if "pe" in census:
        return "executables but no RAGE archives found"
    return "no RAGE archives found"


def _load_hashes(path: Path) -> set[int]:
    data = path.read_bytes()
    text = data[:4096]
    hashes: set[int] = set()
    if all(32 <= b < 127 or b in (9, 10, 13) for b in text):
        for tok in re.findall(r"0x[0-9A-Fa-f]{1,8}|\b[0-9A-Fa-f]{8}\b|-?\b\d{1,10}\b", data.decode("ascii", "ignore")):
            try:
                v = int(tok, 16) if tok.lower().startswith("0x") or re.fullmatch(r"[0-9A-Fa-f]{8}", tok) and not tok.isdigit() else int(tok)
            except ValueError:
                continue
            hashes.add(v & 0xFFFFFFFF)
    else:
        hashes.update(struct.unpack_from(f"<{len(data) // 4}I", data))
    hashes.discard(0)
    return hashes


def _candidates(sources: list[Path], game_index: bool, variants: bool) -> dict[str, str]:
    """name -> where it came from."""
    names: dict[str, str] = {}

    def add(n: str, src: str):
        n = n.strip().lower()
        if n and len(n) < 200:
            names.setdefault(n, src)

    for s in sources:
        if not s.is_file():
            raise ForgeError(f"no wordlist: {s}", "pass existing files with --words")
        for line in s.read_text(encoding="utf-8", errors="replace").splitlines():
            for tok in re.split(r"[\s,;]+", line):
                if re.fullmatch(r"[A-Za-z0-9_@./\\-]{2,}", tok):
                    add(tok, s.name)
                    stem = tok.replace("\\", "/").rsplit("/", 1)[-1]
                    add(stem, s.name)
                    if "." in stem:
                        add(stem.rsplit(".", 1)[0], s.name)
    if game_index:
        try:
            from .index import _load, current_index
            rows, stems = _load(str(current_index()))
            for stem in stems:
                add(stem, "gta5-index")
        except ForgeError:
            pass
    if variants:
        base = list(names.items())
        for n, src in base:
            for suf in ("_hi", "_lod", "_slod1", "_g9ec", "+hi", "_a", "_b", "_01", "_02", "_vi", "_gta6"):
                add(n + suf, src + "+variant")
            if n.startswith("gta5_") or n.startswith("v_"):
                add(n.split("_", 1)[1], src + "+variant")
    return names


def names(hash_file: Path, words: list[Path], game_index: bool = True, variants: bool = True, out: Path | None = None,
          limit: int = 200) -> dict:
    if not hash_file.is_file():
        raise ForgeError(f"no hash file: {hash_file}", "pass a text list (hex/decimal) or a raw u32 table")
    wanted = _load_hashes(hash_file)
    if not wanted:
        raise ForgeError("no hashes found in the file", "one hash per line, 0x-hex, 8-digit hex or decimal; or a binary u32 table")
    cands = _candidates(words, game_index, variants)
    found = {}
    for n, src in cands.items():
        h = int(joaat(n), 16)
        if h in wanted and h not in found:
            found[h] = {"hash": f"0x{h:08x}", "name": n, "source": src}
    result = {"hashes": len(wanted), "candidates": len(cands), "recovered": len(found),
              "rate": round(len(found) / len(wanted), 4), "matches": list(found.values())[:limit],
              "unresolved_sample": [f"0x{h:08x}" for h in sorted(wanted - set(found))[:50]]}
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(f"{m['hash']}\t{m['name']}" for m in found.values()) + "\n", encoding="utf-8")
        result["out"] = str(out)
    return result


def checklist(folder: Path | None) -> dict:
    items = [
        ("build", "record title version, executable hash, runtime"),
        ("archives", "list archives and headers; compare with RPF7"),
        ("explorer", "does a community explorer open them (6ixpack here)"),
        ("cut_content", "search archive tables for casino/activity/adult terms"),
        ("script_vm", "script container format; hashed natives?"),
        ("native_table", "native registration table; hash scheme vs GTA V/RDR2"),
        ("entity_pool", "ped/entity pool and player position from memory"),
        ("saves", "save directory and write path"),
        ("nude_models", "ped models with full-body nude variants; strip club / nudist resort models"),
        ("anim_dicts", "anim dicts for intimacy, dance, seated cards/dice, darts, drinking"),
        ("casinos", "casino interiors: archetypes, collision, props behind the doors"),
        ("dll_call", "a DLL in the runtime calls one harmless title function (go/no-go for the adapter)"),
    ]
    res = []
    pr = None
    if folder is not None:
        pr = probe(folder, nested=True)
    for i, (key, what) in enumerate(items, 1):
        st, ev = "manual", None
        if pr is not None:
            if key == "build":
                titles = [e for e in pr["executables"] if e["looks_like_title"]]
                st, ev = ("done", titles[:3]) if titles else ("blocked", "no title executable found")
            elif key == "archives":
                st, ev = ("done", pr["archives"]["by_format"]) if pr["archives"]["count"] else ("blocked", "no archives")
            elif key == "explorer":
                ex = find_tool("6to5m")
                st, ev = ("ready", ex) if ex and "rpf9" in pr["archives"]["by_format"] else ("blocked", "need 6ixpack + RPF9 files")
            elif key in ("cut_content", "nude_models", "anim_dicts", "casinos"):
                st, ev = "ready", f"gtaforge vi extract <archive> --list, then search for: {', '.join(CUT_CONTENT_TERMS)}"
            elif key == "native_table":
                st, ev = "ready", "dump the table, then: gtaforge vi names <hashes> --words <GTA V native names>"
        res.append({"n": i, "check": key, "what": what, "status": st, "evidence": ev})
    return {"folder": str(folder) if folder else None, "checks": res, "probe_report": pr["report"] if pr else None,
            "source": "GTA 6.5 docs/GTA6-TOOLING-WATCH.md section 4"}


WATCH = ("Marvisak/VIctory", "DesignWithTommy/6to5m", "nullbrik/RageForge", "Ahmet-Dedeler/awesome-gta6-reverse-engineering",
         "RatPrez/ragekit", "crxhvrd/CodeWalkerProjects", "scripthookvdotnet/scripthookvdotnet")


def watch(repos=WATCH, timeout: int = 20) -> dict:
    """Public GitHub API (no token, nothing personal sent): is each watched tool alive, what moved, latest release."""
    import urllib.error
    import urllib.request

    def get(url):
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "gta-forge"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j
            return _j.loads(r.read().decode("utf-8"))

    out = []
    for repo in repos:
        row = {"repo": repo}
        try:
            info = get(f"https://api.github.com/repos/{repo}")
            row.update(status="alive", pushed_at=info.get("pushed_at"), archived=info.get("archived"),
                       stars=info.get("stargazers_count"), license=(info.get("license") or {}).get("spdx_id"))
            try:
                rel = get(f"https://api.github.com/repos/{repo}/releases/latest")
                row["latest_release"] = {"tag": rel.get("tag_name"), "published_at": rel.get("published_at")}
            except urllib.error.HTTPError:
                row["latest_release"] = None
        except urllib.error.HTTPError as e:
            row["status"] = "gone (404)" if e.code == 404 else f"http {e.code}"
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            row["status"] = f"unreachable: {e}"
        out.append(row)
    return {"checked": time.strftime("%Y-%m-%d %H:%M:%S"), "repos": out,
            "note": "a repo that vanished may be a takedown: keep the local clone (vendor/)"}


def run(args) -> dict:
    a = args.action
    if a == "status":
        return _status()
    if a == "watch":
        return watch()
    if a == "tools":
        md = VENDOR / "awesome-gta6-reverse-engineering-main" / "README.md"
        if not md.is_file():
            raise ForgeError("index not vendored", "clone Ahmet-Dedeler/awesome-gta6-reverse-engineering into vendor/")
        links = sorted(set(re.findall(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", md.read_text(encoding="utf-8", errors="replace"))))
        return {"index": str(md), "projects": len(links), "links": links}
    if a == "build-6to5m":
        cargo = find_tool("cargo")
        src = VENDOR / "6to5m-main"
        if not cargo:
            raise ForgeError("cargo not found", "install Rust (rustup) then retry")
        if not (src / "Cargo.toml").is_file():
            raise ForgeError("6to5m source not vendored", "clone DesignWithTommy/6to5m into vendor/6to5m-main")
        r = run_proc([cargo, "build", "--release"], cwd=src, timeout=3600)
        exe = src / "target" / "release" / ("6ixpack.exe" if os.name == "nt" else "6ixpack")
        return {"engine": "6to5m", "code": r["code"], "log": (r["stderr"] or "").strip().splitlines()[-10:],
                "binary": str(exe) if exe.is_file() else None,
                "evidence": {"compile": "passed" if r["code"] == 0 and exe.is_file() else "failed"}}
    target = Path(args.target) if getattr(args, "target", None) else None
    if a == "probe":
        if target is None:
            raise ForgeError("pass a folder or file", "gtaforge vi probe <game folder or dump>")
        return probe(target, Path(args.out) if args.out else None, max_files=args.limit or 200_000)
    if a == "names":
        if target is None:
            raise ForgeError("pass a hash list", "gtaforge vi names hashes.txt --words names.txt [--words more.txt]")
        return names(target, [Path(w) for w in (args.words or [])], game_index=not args.no_index,
                     out=Path(args.out) if args.out else None)
    if a == "checklist":
        return checklist(target)
    if a == "extract":
        exe = find_tool("6to5m")
        if not exe:
            raise ForgeError("6ixpack not found", "gtaforge vi build-6to5m, or set SIXPACK")
        if target is None or not target.exists():
            raise ForgeError("pass an RPF9 file", "gtaforge vi extract <file.rpf> --out <empty folder> [--list]")
        argv = [exe] + (["-n"] if args.list else []) + [str(target)] + ([args.out] if args.out and not args.list else [])
        r = run_proc(argv, timeout=7200)
        if r["code"]:
            raise ForgeError(f"6ixpack failed: {(r['stderr'] or r['stdout']).strip()[-300:]}", "6ixpack --help")
        return {"engine": "6ixpack", "out": args.out, "log": r["stdout"].strip().splitlines()[-30:]}
    raise ForgeError(f"unknown action {a}", "status | tools | build-6to5m | probe | names | checklist | extract")
