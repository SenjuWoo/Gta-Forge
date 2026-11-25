# AGENTS.md - GTA Forge runbook

## Sources of truth

- Version: `src/gtaforge/__init__.py` (`__version__`). Mirrors checked by tests:
  `CHANGELOG.md`, `STATE.md`, `README.md`, `skills/gta-forge/SKILL.md`.
- Domain facts: `src/gtaforge/knowledge/*.json` (facts with tier + source,
  frameworks, tools, routes, errors, vi watch) and `natives.json.gz`
  (alloc8or gta5-nativedb-data). Change data, not prose.
- Installed game beats docs: `gtaforge game`, `gtaforge rpf`, `gtaforge find`
  read the install/index before anything is written against a remembered name.
- Personal paths live in `%LOCALAPPDATA%\GTAForge\config.json`, never in the repo.

## Where the logic lives

| Module | Job |
|---|---|
| `cli.py` | argparse (errors -> exit 2), JSON, exit codes |
| `game.py` | discovery, editions, frameworks, inventory, GTA VI folders |
| `doctor.py`, `knowledge.py` | health, routing, docs, facts |
| `rpf7.py`, `rpf9.py`, `rpf.py` | archive formats; python vs ragekit routing; keys |
| `index.py` | asset index of the installed game |
| `natives.py`, `anims.py`, `menyoo.py` | lookups (real data only), natives.h generator |
| `scripts.py`, `check.py` | static checks |
| `compilemod.py`, `build.py` | MSVC/CMake and dotnet builds, archive packing |
| `project.py`, `package.py`, `deploy.py` | manifest + payload, zip, deploy receipt |
| `bindings.py`, `vi.py` | binding coverage; GTA VI kit |
| `logs.py`, `conflicts.py`, `nexus.py` | test loop and release text |

## Loop

1. `python tests/run_tests.py` (offline + real tests that skip without the game).
2. A fix starts with a failing test. Format facts come from a primary source
   (ragekit / 6to5m source, the installed files), cited in the module docstring.
3. Real install: `gtaforge doctor`, `gtaforge new T --kind <each>` + `gtaforge check --compile`.
4. Update `CHANGELOG.md`, `STATE.md`, README, SKILL and `__version__` together.
5. Bad input is exit 1/2 with a fix, never a traceback (the fuzz test enforces it).

## Boundaries

Read-only on the game except `deploy` (receipt + original backups, write by rename).
No uploads, no game launch, no GTA Online, no invented asset/native names, no keys in the repo.
