# Overview

GTA Forge makes, checks and ships **single-player** GTA V mods (Legacy and
Enhanced) and prepares for GTA VI when a PC-runnable build exists. It reads
facts from the installed game and from versioned data, never from memory.

- Every command prints JSON. Exit 0 ok, 1 findings, 2 named failure, 3 bug.
- `gtaforge doctor` first. `gtaforge plan "<request>"` routes before writing.
- `gtaforge knowledge` lists these docs; `gtaforge facts` queries the fact table.
- Single-player only. **Never mod GTA Online** (ban risk; ScriptHookV closes it).

Surfaces: C++ asi (ScriptHookV), C# (SHVDN), Lua (FiveM/RedM, not SP), XML
(Menyoo), archives (RPF7 on V, RPF9 on VI), models (CodeWalker/Sollumz), maps
and MLO interiors, anim dicts, casino/activity logic.