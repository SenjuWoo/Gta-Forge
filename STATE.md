# STATE

Version: **1.0.0** (2026-11-24)
Last known good: 1.0.0 (this commit); previous release v0.2.0.

## Goal

Local-first GTA V mod toolkit that is correct on the real install (archives,
asset index, natives, builds, release loop) plus a GTA VI day-one kit that
already runs and is tested before any GTA VI file exists. Plan: PLAN.md.

## Done (1.0.0) - verified

- Offline suite: `python tests/run_tests.py` (43 offline + 9 real tests).
- Real install (Enhanced 1.0.1158.16): every top-level RPF reads as RPF7/NG;
  `rpf keys` (exe + CodeWalker magic.dat) -> ragekit lists and extracts retail
  archives; `index build` = 123 archives, 388,893 entries, 4.7 s;
  `find` confirms the strip-club, street, casino-dealer dicts, adder, prop_bench_01a.
- Real builds: cpp template -> `.asi` importing ScriptHookV.dll/scriptRegister
  (MSVC 18 BuildTools via vswhere, Ninja, SDK 1.0.617.1a, generated natives.h
  with all 6,701 natives); shvdn template -> DLL against SHVDN 3.9.0.6.
- GTA VI kit: probe/checklist/names on synthetic RPF9; probe on GTA V as a
  control; names recovers 2,000/2,000 real GTA V model hashes; `vi watch` live.

## Build / run

- Install: `powershell -ExecutionPolicy Bypass -File Install.ps1` (venv, launcher on PATH, skill).
- Run from source: `gtaforge.cmd <command>` or `python -m gtaforge` with `src` on PYTHONPATH.
- Tests: `python tests/run_tests.py` (`GTA_FORGE_REAL=0` skips real-install tests).
- Logs: none written by default; every command prints JSON. Forge data:
  `%LOCALAPPDATA%\GTAForge` (index/, deploy/, vi/, keys/magic.dat, config.json); game keys in `~/.ragekit/keys`.

## Next

- When ScriptHookV supports the installed Enhanced build (or a pinned 1158.13
  copy exists): first load test of a deployed asi; record it as load evidence.
- When GTA VI files exist: `gtaforge vi checklist <folder>` and follow it.

## Gaps

- No load/gameplay evidence: ScriptHookV does not support Enhanced 1.0.1158.16 yet (doctor warns).
- luajit not installed: `script lua` names the fix.
- No GTA VI runtime test (none can exist yet).
