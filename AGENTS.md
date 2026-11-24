# AGENTS.md - GTA Forge runbook

## Sources of truth

- Version: `src/gtaforge/__init__.py` (`__version__`). Mirrors checked by tests:
  `CHANGELOG.md`, `STATE.md`, `skills/gta-forge/SKILL.md`.
- Domain facts: `src/gtaforge/knowledge/*.json` (facts with tier + source,
  frameworks, tools, routes, errors, natives subset, vi watch). Change data, not prose.
- Installed game beats docs: `gtaforge game`, `gtaforge rpf`, `gtaforge anim`
  read the install/index before anything is written against a remembered name.

## Where the logic lives

| Module | Job |
|---|---|
| `cli.py` | argparse, JSON, exit codes |
| `game.py` | discovery (arg, env, Steam, Epic, Rockstar), editions, frameworks, inventory |
| `doctor.py`, `knowledge.py` | health, routing, docs, facts |
| `natives.py`, `anims.py`, `menyoo.py` | lookups (real data only) |
| `rpf.py`, `vi.py` | archives (CodeWalker/ragekit/6to5m), GTA VI watch |
| `scripts.py`, `compilemod.py`, `build.py` | static checks, CMake/dotnet builds |
| `project.py`, `check.py` | manifest, templates, bump, validation |
| `package.py`, `deploy.py`, `logs.py`, `conflicts.py`, `nexus.py` | release and test loop |

## Loop

1. `python tests/run_tests.py` (offline; fake game tree).
2. A fix starts with a failing test.
3. Real install: `gtaforge doctor`, `gtaforge new T --kind <each>` + `gtaforge check --compile`.
4. Update `CHANGELOG.md`, `STATE.md`, bump `__version__` together.
5. Bad input is exit 1/2, never a crash.

## Boundaries

Read-only on the game except `deploy` (receipt + backups, write by rename).
No uploads, no game launch, no GTA Online, no invented asset/native names.