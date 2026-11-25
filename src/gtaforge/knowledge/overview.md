# Overview

GTA Forge makes, checks and ships **single-player** GTA V mods (Legacy and
Enhanced) and carries a GTA VI day-one kit. It reads facts from the installed
game (archives, asset index, exe version) and from versioned data (native DB,
facts with sources), never from memory.

- Every command prints JSON. Exit 0 ok, 1 findings, 2 named failure with a fix, 3 bug.
- Start: `gtaforge doctor`, then `gtaforge plan "<request>"`.
- Confirm names: `gtaforge find <asset>`, `gtaforge natives <name>`, `gtaforge anim --dict <d>`.
- Build loop: `new` -> `check --compile` -> `package` -> `validate` -> `deploy` -> `logs`.
- Never mod GTA Online (ban risk; ScriptHookV closes the game there).

Surfaces: C++ asi (ScriptHookV), C# (SHVDN v3), Menyoo Spooner XML, Lua
(FiveM, not SP), archives (RPF7 read/pack; RPF9 probe), models via ragekit /
CodeWalker / Sollumz, maps and MLO interiors, anim dicts, binding tables for
engine-agnostic mods (bindings.md), GTA VI kit (vi.md).
