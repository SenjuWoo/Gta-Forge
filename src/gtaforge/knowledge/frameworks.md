# Frameworks and the rig

| Need | Install | Notes |
|---|---|---|
| Native API | ScriptHookV (`ScriptHookV.dll`) + SDK | version must list your exe (doctor warns) |
| ASI loader | `dinput8.dll` (Legacy) or `xinput1_4.dll` / Ultimate ASI Loader (Enhanced) | one loader only |
| .NET scripts | ScriptHookVDotNet **Enhanced** build on Enhanced | 2.x and 3.x are not interchangeable |
| Loose-file data | onigiri (Enhanced): files under `onigiri/` override archives | no RPF edit needed for data/audio |
| Archive edit | CodeWalker (GUI) / ragekit (CLI) | back up first |
| Models | Blender 5.x + Sollumz 2.9.1 | import from the game install |
| Lua | FiveM/RedM server | separate ecosystem, not a SP mod |

Rig rules: launch with `-nobattleye` (args.txt), test on a copy of the game or a
pinned build, keep a clean `scripts/` baseline, and read `gtaforge logs` after
every run. Evidence tiers: compile, load, gameplay are separate claims.