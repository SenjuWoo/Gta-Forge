# Formats

| Thing | GTA V PC | GTA VI (console) |
|---|---|---|
| Archive | RPF7, encrypted TOC (names are joaat hashes) | RPF9; TTPF textures (BCPack), ADAT/AWC audio |
| Scripts | `.ysc` in SCRIPT.rpf, native = joaat(name); decompiled C for reference | unknown; assume hashed natives |
| Model | Drawable `ydr`/`yft`, `ytyp`, `ymap` placements | RPF9 drawables -> OBJ/GLB (6to5m, RageForge) |
| Interior (MLO) | shell + portals + rooms in a ymap, interior proxy | same concept, RPF9 |
| Lua | not SP; FiveM `fxmanifest.lua` | FiveM only |

`gtaforge facts formats` prints the table with sources. A name is never
invented: confirm in CodeWalker, the anim index, or the native DB.