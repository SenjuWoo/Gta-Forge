goal: GTA Forge 1.0 - every command correct on the real GTA V Enhanced install, real NG archive reads, real SHV/SHVDN builds, and a GTA VI day-one kit (RPF9 probe, name recovery, checklist) proven on fixtures and on the V install as a control.

# PLAN - GTA Forge 1.0

## Audit of 0.2.0 (2026-11-24, commit 742371d)

| Defect | Proof |
|---|---|
| `def run(args)` in rpf/vi/build/compilemod/scripts shadows `util.run`; every external tool call recurses or raises TypeError (exit 3) | read: `run([cmake,...], timeout=300)` calls `compilemod.run` |
| RPF7 magic compared as `b"RPF7"`; real files store `7FPR` -> every real archive rejected | real header bytes of common.rpf: `7FPR`, enc 0x0FEFFFFF |
| ragekit invoked as `rk list <t>`; real CLI is `ragekit rpf ls <t> --enhanced` and needs NG keys | `ragekit --help`; keys error on common.rpf |
| `hash --tweakdb` imports a function that does not exist in knowledge.py (Cyberpunk leftover) | read cli.py:151 |
| C++ template: native calls from a raw CreateThread, no scriptRegister, un-namespaced natives; cannot compile against the SDK and would crash if it did | read templates/cpp/src/main.cpp vs SDK inc/main.h |
| compile builds in a temp copy then deletes it: the .asi is lost; Ninja without vcvars has no compiler | read compilemod.py; `cl` not on PATH |
| package/deploy ship the source tree (main.cpp, CMakeLists.txt) into the game root | test asserts 3 files incl. src/main.cpp |
| deploy twice backs up its own v1 as the "original"; remove restores the mod instead of removing it | read deploy.py |
| natives.json: 201-name subset, params double-encoded as JSON strings | head of natives.json |
| routes point at docs that do not exist (map.md, logs.md); docs are 5-line stubs | ls knowledge/ |
| STATE claims RPF / CodeWalker work; nothing was run on a real archive | no evidence in repo |

## Tasks

| ID | Task | Status | Depends on | Verify | Evidence |
|---|---|---|---|---|---|
| F01 | Fix shadowed `run` (rename util.run -> run_proc), `hash --joaat` with a reference vector | complete | - | cmd:python tests/run_tests.py | cmd:python tests/run_tests.py @ f761a0c exit=0 |
| F02 | RPF7 reader in Python: header (7FPR, count, names len, encryption kind), full TOC + names + extract for OPEN/NONE archives, resource RSC7 header rebuild; RPF7 OPEN writer (`rpf pack`); RPF9 header reader (6to5m layout) | complete | F01 | cmd:python tests/run_tests.py | cmd:python tests/run_tests.py @ f761a0c exit=0 |
| F03 | ragekit route: correct argv, `--enhanced/--legacy` from the game, `rpf keys` step that takes magic.dat from the staged CodeWalker.Core.dll; real `rpf ls/extract` on the installed game | complete | F02 | cmd:gtaforge rpf list common.rpf | cmd:gtaforge rpf list common.rpf @ f761a0c exit=0 (ragekit, NG, 704 entries) |
| F04 | Asset index: `index build` (every archive, nested, via ragekit TSV) -> `find <name>` confirms dicts/models/textures exist in the installed game | complete | F03 | cmd:gtaforge find mini@strip_club@idles@stripper | cmd:gtaforge find mini@strip_club@idles@stripper @ f761a0c exit=0 (index 388,893 entries) |
| F05 | Full native DB (alloc8or gta5-nativedb-data), clean params, gz; exact/hash search; script check validates `NS::NAME(` and `Hash.NAME` / `0x` calls + SHVDN arg counts | complete | F01 | cmd:python tests/run_tests.py | cmd:python tests/run_tests.py @ f761a0c exit=0 |
| F06 | Templates that compile: cpp (scriptRegister, namespaced natives, /MT), shvdn (SHVDN3 ref from game or env); compile in project/build with vcvars capture; outputs kept | complete | F01 | cmd:gtaforge check --compile (real SDK) | cmd:python -m unittest tests.test_real.TestRealCompile @ f761a0c exit=0 (real .asi + SHVDN dll) |
| F07 | Payload model: manifest `payload` [{from, to}] per kind; package/deploy ship build outputs only; deploy keeps first originals, path-traversal guard, `--dry-run` | complete | F06 | cmd:python tests/run_tests.py | cmd:python tests/run_tests.py @ f761a0c exit=0 |
| F08 | GTA VI kit: `vi probe <folder>` (exes, RPF7/8/9 magic census, TTPF/AWC/RSC signatures, sizes, report), `vi names` (joaat dictionary recovery against hashes), `vi checklist` (12 first checks, auto where possible), discovery of a GTA VI folder | complete | F02 | cmd:python tests/run_tests.py | cmd:python tests/run_tests.py @ f761a0c exit=0 |
| F09 | `bindings check`: binding-key table vs the asset index / anim index (GTA 6.5 T37 contract), coverage % per module | complete | F04 | cmd:python tests/run_tests.py | cmd:python tests/run_tests.py @ f761a0c exit=0 |
| F10 | Doctor: MSVC via vswhere, SHV SDK, keys state, Enhanced loader name, `-nobattleye`, VI runtime section; knowledge docs rewritten; every route doc exists (test) | complete | F03 | cmd:gtaforge doctor | cmd:gtaforge doctor @ f761a0c exit=1 (correct findings: ScriptHookV absent and unsupported on 1.0.1158.16; all sections present) |
| F11 | Test suite: every command via CLI, no exit 3 on bad input (fuzz), real-install tests (skipped without the game), version mirrors | complete | F01-F10 | cmd:python tests/run_tests.py | cmd:python tests/run_tests.py @ f761a0c exit=0 (53 tests) |
| F12 | 1.0.0: version, CHANGELOG, README, SKILL, STATE; install; CI green on the pushed SHA; release | pending | F11 | cmd:gh run list -R SenjuWoo/Gta-Forge | - |

## Decisions

| Chosen | Rejected | Why |
|---|---|---|
| Python OPEN-archive reader/writer + ragekit for NG | Python NG decryption | NG needs keys + 272 tables; ragekit already does it and is built here |
| magic.dat read from the owner's staged CodeWalker.Core.dll at run time, keys in `~/.ragekit/keys` | shipping keys | keys are the owner's game data; never committed |
| Build in `<project>/build` (git-ignored) with captured vcvars env | temp copy | outputs are the payload |
| Payload rules in gtaforge.json | ship the tree minus a denylist | a denylist ships source; an allowlist ships only what the game loads |
| VI kit works on any folder and is tested on synthetic RPF9 + the V install as a control | waiting for files | day-one value comes from tools that already ran |

## Assumptions

| Assumption | Check |
|---|---|
| alloc8or natives.json is the current V native DB | fetch + compare counts with fivem DB |
| GTA VI archives keep the `9FPR` magic seen in the console dump | 6to5m source container.rs; first real file |
| GTA VI names are joaat hashes like V/RDR2 | `vi names` on the first TOC with a known-name dictionary |

## Risks

- ragekit NOASSERTION licence: used locally, never redistributed.
- A GTA V patch can move NG tables: `rpf keys` re-runs from magic.dat.

## Log

- 2026-11-24: 0.2.0 audit (table above); rebuilt modules, 53 tests; real install: keys via ragekit + CodeWalker magic.dat, index 123 archives/388,893 entries in 4.7 s, real .asi and SHVDN builds; launcher exit-code bug found and fixed during install check.
