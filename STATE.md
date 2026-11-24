# STATE

Version: **0.2.0** (2026-11-24)

## Goal

Local-first GTA V mod toolkit (asi/SHVDN/Lua/XML, RPF, models, maps/MLO, anims,
casino/activities), GTA VI watch. Facts from the installed game.

## Done (0.1.0) - verified

- 16/16 offline tests (`python tests/run_tests.py`, exit 0).
- Installed via Install.ps1; `gtaforge doctor` on the real Enhanced install:
  edition enhanced 1.0.1158.16, warn missing ScriptHookV/asi loader (true), exit 1.
- `gtaforge menyoo index` on the owner's Menyoo lists: 19,771 dicts / 269,420 clips.
- `gtaforge vi tools`: 78 projects from the vendored RPF9 index.
- `gtaforge capabilities`: 24 commands. Skill installed to .claude/.agents.
- Local git commit fd62b3a. No remote (publication not requested).

## Next

- Build ragekit (vendor/ragekit-main) and 6to5m (`gtaforge vi build-6to5m`);
  point CODEWALKER at the staged CodeWalker in the GTA 6.5 workspace.
- Real-install smoke of new+check+package on a scratch project.

## Gaps

- No GTA VI runtime test (none exists). Native DB is a 201-name subset.
- ragekit/6to5m/CodeWalker not on PATH yet (doctor reports them missing).