---
name: gta-forge
description: Use when making, checking or shipping GTA V mods (ScriptHookV asi, SHVDN, Lua/FiveM, Menyoo XML, RPF archives, models, maps/MLO, anims, casino/activities) or checking GTA VI PC readiness. Local-first CLI, JSON output.
---
# GTA Forge

Start every task with the CLI, not memory:

1. `gtaforge doctor` - game, frameworks, tools (separate sections).
2. `gtaforge plan "<request>"` - route, docs, what to avoid.
3. `gtaforge knowledge <doc>` / `gtaforge facts <key>` / `gtaforge natives <name>` / `gtaforge anim --pattern <part>`.
4. `gtaforge new <name> --kind cpp|shvdn|lua|xml|menyoo`, then `gtaforge check --compile`.
5. `gtaforge package`, `gtaforge validate <zip>`, `gtaforge deploy` (test), `gtaforge logs`.

Rules: single-player only (never GTA Online); never invent an asset/native/anim
name (confirm in the index or CodeWalker); evidence tiers (compile/load/gameplay)
are reported separately; the game is read-only except `deploy`.