# Changelog

## 1.2.0 - 2026-11-24
- `gtaforge anim clips --dict <d>`: clip names read from the installed game (ragekit pulls the .ycd, `ragekit info -v` lists it), cached per game version.
- `gtaforge anim build --batch <dicts.txt>`: game clip index for many dicts (Enhanced 1.0.1158.16: 3,485 dicts / 51,401 clips in under a minute) at `<home>/anim_index_game/`; `anim` lookups and `bindings` clip checks use it automatically.
- Anim index keys are matched case-insensitively.

## 1.1.1 - 2026-11-24
- Exe/dll versions are read from the PE version resource in Python (cached, any OS) instead of one PowerShell process per call; `find --batch` over 2,745 names went from minutes to 1.4 s. Output matches Windows' FileVersion on the installed game, ScriptHookV and SHVDN files.

## 1.1.0 - 2026-11-24
- `gtaforge find --batch <file>`: many exact lookups with one index load; per name: found, archive paths, kinds, and whether an Enhanced-generation `*_g9ec` pack also holds it. Exit 1 when any name is missing. Used by the GTA 6.5 V-base inventory.

## 1.0.0 - 2026-11-24
Rebuilt after an audit of 0.2.0 against the real Enhanced install and toolchain.

Fixed (0.2.0 defects)
- Every external tool call crashed: `run(args)` entry points shadowed the process helper (now `run_proc`).
- RPF7 magic was compared as `RPF7`; real archives store `7FPR`, so every game archive was rejected.
- ragekit was called with a CLI it does not have; now `ragekit rpf ls|cat --enhanced|--legacy`.
- `hash --tweakdb` imported a missing function (Cyberpunk leftover); now `hash --joaat`.
- C++ template called natives from a raw thread without `scriptRegister`, un-namespaced: it could not compile and would crash. Now a correct ScriptHookV entry point, built against the SDK.
- `compile` built in a temp copy and deleted the output, and had no compiler without a dev prompt.
- `package`/`deploy` shipped the source tree into the game; a second deploy backed up the mod as the "original".
- `asi_loader` required all three loader dlls at once; `shv_supported` was never a boolean, so the unsupported-patch warning never fired.
- Native DB was a 201-name subset with double-encoded params; routes pointed at missing docs.

Added
- Pure-Python RPF7 reader (list/find/extract incl. nested, resource RSC7 header rebuild) and OPEN writer (`rpf pack`, `build` packs `<name>.rpf/` folders); RPF9 header reader.
- `rpf keys`: game keys from your own exe + CodeWalker's magic.dat (read from the staged CodeWalker.Core.dll); NG retail archives through ragekit.
- Asset index (`index build`, `find`): every entry of every archive, nested (Enhanced 1.0.1158.16: 123 archives, 388,893 entries).
- Full native DB (6,701, alloc8or) with old names; `natives --header` writes a current natives.h with a variadic invoker (natives take up to 32 args; the SDK caller stops at 25).
- Static checks: native exists, namespace, argument count for C++ and SHVDN; entry-point rules; Menyoo ModelHash = joaat(HashName).
- MSVC discovery (vswhere + captured vcvars64), CMake + Ninja builds into `build/`; SHVDN v3 builds with the .NET SDK and reference assemblies.
- Payload rules in gtaforge.json (schema 2); deterministic zips; validation of path escapes, framework dlls, sources, secrets; deploy dry-run, original backups kept across redeploys, stale-file and empty-folder cleanup, payload escape guard.
- Menyoo Spooner template; `bindings` coverage checker (content keys -> game assets).
- GTA VI kit: `vi probe` (content-signature census, RPF9 headers + nested archives), `vi checklist` (12 first checks), `vi names` (joaat recovery), `vi extract` (6ixpack), `vi watch` (live GitHub status of the community tools).
- `doctor` sections: build toolchain, archive keys, asset index, GTA VI folders; personal tool dirs in `%LOCALAPPDATA%\GTAForge\config.json` instead of machine paths in the repo.
- Bad usage and environment errors are exit 2 with a fix; a fuzz test runs every command with bad input.
- Real tests (skip without the game/tools): retail archive headers, ragekit list/extract, index lookups, GTA V control probe, name recovery, real C++ and SHVDN template builds.

## 0.2.0 - 2026-11-24
- Tool discovery: `GTA_FORGE_TOOLS` / `%LOCALAPPDATA%\GTAForge\tools` scan;
  staged CodeWalker, ragekit, 6to5m and the ScriptHookV SDK are found automatically.
- `vi build-6to5m` no longer forces `--offline`.
- README + icon (`tools/make_icon.py`), CI badge, release workflow.
- Verified online: ScriptHookV still 1158.13, CodeWalker v1.0.0, Sollumz v2.9.1.
- Built ragekit (`rk.exe`) and 6to5m (`6ixpack.exe`); doctor finds CodeWalker,
  ragekit, 6to5m and the SHV SDK via the staged tools dir.

## 0.1.0 - 2026-11-24
- First release: GTA V mod toolkit (asi/SHVDN/Lua/XML, RPF7/RPF9 watch, anim
  index, casino/activity routing, package/deploy/logs/conflicts), JSON CLI,
  knowledge data with sources, templates, vendored GTA VI tool index.