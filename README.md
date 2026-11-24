# GTA Forge

A local toolkit for making, checking and shipping **GTA V** mods (Legacy and
Enhanced): C++ asi (ScriptHookV), C# (SHVDN), Lua (FiveM/RedM), XML (Menyoo),
RPF7/RPF9 archives, models, maps and MLO interiors, animation dictionaries,
casino and activity logic. GTA VI is a read-only watch until a PC-runnable
build and file tools exist.

It reads facts from **your installed game** and from versioned data. Every
command prints JSON with a stable exit code (0 ok, 1 findings, 2 named failure,
3 bug).

| Need | Command |
|---|---|
| Healthy? Game, frameworks, tools | `gtaforge doctor` |
| What can it do? | `gtaforge capabilities` |
| Route my request | `gtaforge plan "add a blackjack table"` |
| What is installed? | `gtaforge game` |
| Native hash / params | `gtaforge natives TASK_PLAY_ANIM` |
| Animation dict / clip | `gtaforge anim --pattern strip_club` |
| Archive | `gtaforge rpf info <archive.rpf>` |
| Script project | `gtaforge new MyMod --kind cpp` then `gtaforge compile` |
| Validate | `gtaforge check --compile` |
| Package / validate zip | `gtaforge package`, `gtaforge validate <zip>` |
| Install for a test / remove | `gtaforge deploy`, `gtaforge deploy --remove` |
| Logs / conflicts | `gtaforge logs`, `gtaforge conflicts` |
| Menyoo lists | `gtaforge menyoo index --folder <menyooStuff>` |
| GTA VI readiness | `gtaforge vi status`, `gtaforge vi tools` |

Single-player only. Never mod GTA Online. The forge never uploads, never
launches the game, and writes to the game only on `gtaforge deploy`.