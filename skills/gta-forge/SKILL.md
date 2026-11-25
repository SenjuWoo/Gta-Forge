---
name: gta-forge
description: Use when making, checking or shipping GTA V mods (ScriptHookV asi, SHVDN, Menyoo XML, Lua/FiveM, RPF archives, models, maps/MLO, anims, casino/activities, binding tables) or preparing for GTA VI files (RPF9 probe, name recovery, first checks). Local-first CLI, JSON output.
---
# GTA Forge (1.1.1)

Start every task with the CLI, not memory:

1. `gtaforge doctor` - game, build toolchain, archive keys, asset index, GTA VI (separate sections).
2. `gtaforge plan "<request>"` - route, docs, what to avoid.
3. Confirm every name before writing it:
   `gtaforge find <asset> [--ext .ycd|.ydr|.ytd]` (asset index; `gtaforge rpf keys` + `gtaforge index build` once),
   `gtaforge natives <name|0xhash>`, `gtaforge anim --dict <d>`, `gtaforge hash --joaat <name>`.
4. `gtaforge new <name> --kind cpp|shvdn|menyoo|xml|lua --target-game enhanced`, then `gtaforge check --compile`.
5. `gtaforge package`, `gtaforge validate <zip>`, `gtaforge deploy --dry-run`, `gtaforge deploy`, `gtaforge logs`.
6. Engine-agnostic mods: `gtaforge bindings <keys.json> <game table.json>` (coverage per module).
7. GTA VI files: `gtaforge vi probe <folder>`, `vi checklist <folder>`, `vi extract <rpf>`, `vi names <hashes> --words <list>`, `vi watch`.

Rules: single-player only (never GTA Online); never invent an asset/native/anim
name; static/compile/load/gameplay evidence are separate claims; the game is
read-only except `deploy`; archive keys stay on the machine.
