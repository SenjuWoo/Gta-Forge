<div align="center">

<img src="docs/icon.png" alt="GTA Forge" width="132">

# GTA Forge

**A local-first workbench for GTA V mods — and a watchtower for GTA VI.**

[![CI](https://github.com/SenjuWoo/Gta-Forge/actions/workflows/ci.yml/badge.svg)](https://github.com/SenjuWoo/Gta-Forge/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/SenjuWoo/Gta-Forge?include_prereleases)](https://github.com/SenjuWoo/Gta-Forge/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776ab)](pyproject.toml)
[![Platforms](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-06b6d4)](#install)

</div>

GTA Forge turns an idea like *“add a blackjack table”* or *“why does my asi
crash on Enhanced?”* into a route, the real files, and a check you can run. It
reads your **installed game** — editions, frameworks, archives, animation
dictionaries — instead of trusting a wiki page from 2015.

- **JSON on stdout, stable exit codes** (0 ok · 1 findings · 2 named failure · 3 bug). Built for agents and CI, usable by humans.
- **Facts are data with sources.** Native hashes, framework versions, format notes and the GTA VI tool index live in versioned files, not prose.
- **Single-player only.** It never touches GTA Online, never uploads, never launches the game, and writes to the game folder only when you run `deploy`.
- **GTA VI ready when the platform is.** No playable PC build exists yet; the forge ships the RPF9/TTPF tool index and a `6to5m` build command so the day one appears you start from a checklist, not a search.

## Install

**Windows (recommended):** download `START-HERE.bat` from the latest release and
double-click it. It creates a venv, runs the tests, puts `gtaforge` on your PATH
and installs the agent skill.

**Any platform with Python 3.10+:**

```bash
git clone https://github.com/SenjuWoo/Gta-Forge
cd Gta-Forge
python -m pip install -e .
gtaforge doctor
```

`doctor` tells you what is missing (game, ScriptHookV, an asi loader, CodeWalker)
with the fix for each, as separate sections.

## The 60-second tour

```text
gtaforge plan "add a blackjack table to the casino"
gtaforge doctor
gtaforge game
gtaforge natives TASK_PLAY_ANIM
gtaforge anim --pattern strip_club
gtaforge new MyMod --kind cpp
gtaforge check --compile
gtaforge package && gtaforge validate dist/MyMod-0.1.0.zip
gtaforge deploy          # test in game (with -nobattleye)
gtaforge logs --mod MyMod
```

| Need | Command |
|---|---|
| Health: CLI, payload, game, frameworks, tools | `gtaforge doctor` |
| Every command and option | `gtaforge capabilities` |
| Route a request before writing | `gtaforge plan "<request>"` |
| What is installed (edition, patch, SHV, SHVDN, asi) | `gtaforge game` |
| Native hash, return type, params | `gtaforge natives <name\|hash\|namespace>` |
| Animation dict / clip (Menyoo index) | `gtaforge anim --dict <dict> --clip <part>` |
| Archive header / listing / extract | `gtaforge rpf info\|list\|find\|extract <archive>` |
| Script project (asi, SHVDN, Lua, XML, Menyoo) | `gtaforge new <name> --kind cpp\|shvdn\|lua\|xml\|menyoo` |
| Static checks / compile / build | `gtaforge check --compile`, `gtaforge compile`, `gtaforge build` |
| Package, validate, deploy, logs, conflicts | `gtaforge package`, `validate`, `deploy`, `logs`, `conflicts` |
| GTA VI readiness | `gtaforge vi status`, `gtaforge vi tools`, `gtaforge vi build-6to5m` |

## What it covers

| Area | Detail |
|---|---|
| **Scripts** | C++ asi on the ScriptHookV SDK (CMake), C# SHVDN (`dotnet`), Lua for FiveM/RedM (`luajit` syntax check), Menyoo XML |
| **Archives** | RPF7 (GTA V) header + tooling routes; RPF9/TTPF (GTA VI) via 6to5m / RageForge index |
| **Assets** | Drawable/fragment/ymap/ytyp concepts, CodeWalker + Sollumz export path, MLO interior checklist |
| **Animation** | Dict/clip lookup from a Menyoo `PedAnimList` index; adult dicts included, adults-only rule in the docs |
| **Gameplay logic** | Casino rules (blackjack, roulette, poker, slots, wheel), missing-activity routing, economy-cap guidance |
| **Release loop** | Manifest + templates, deterministic runtime-only zip (no tests/logs/STATE), secret scan, deploy receipt + rollback, Nexus BBCode kit |
| **GTA VI** | Platform status, RPF9 tool index (78 projects), `6to5m` build, first-checks list |

## Architecture

```
gtaforge (Python, stdlib only)
  cli.py            JSON + exit codes
  game.py           discovery: arg, env, Steam, Epic, Rockstar; editions; frameworks
  knowledge.py      routing + versioned facts (tier + source)
  natives/anims     real data lookups (fivem natives, Menyoo index)
  rpf/vi            CodeWalker / ragekit / 6to5m routes
  project/check     manifest, templates, validation
  package/deploy    runtime-only zip, receipt, backups, logs, conflicts
  knowledge/*.json  facts, frameworks, tools, routes, errors, vi watch
  templates/        cpp, shvdn, lua, xml, menyoo
```

No MCP server, no daemon, no network at runtime. `vendor/` (git-ignored) holds
optional sources the forge can build: `6to5m`, `ragekit`, the GTA VI reverse
engineering index.

## Evidence, not vibes

Every command reports what was actually exercised. Compile, load and gameplay
are separate claims; a structural check is never reported as a runtime result.
`deploy` writes by copy + rename with a receipt and backups, so a mod manager's
hard links are never written through.

## Status and limits

- GTA V Legacy and Enhanced (tested against Enhanced 1.0.1158.16).
- ScriptHookV support is whatever dev-c.com lists; the forge warns when your
  patch is newer than the hook.
- GTA VI: **no playable PC build exists**. The forge is a watch + file-tool
  index, not a VI mod loader.
- The native DB is a 201-name subset with a link to the full database.

## Contributing

Issues and PRs welcome. Run `python tests/run_tests.py` and `gtaforge doctor`
before opening one. A fix starts with a failing test.

## License

MIT — see [LICENSE](LICENSE). Third-party tools keep their own licences
([THIRD-PARTY.md](THIRD-PARTY.md)); nothing is redistributed except this code.