# RPF archives

GTA V (Legacy and Enhanced) uses RPF7. The first four bytes on disk read `7FPR`
(uint32 0x52504637). Header: entry count, names length, encryption. Retail
archives are **NG** encrypted (0x0FEFFFFF); mod archives are usually **OPEN**
(0x4E45504F) and need no keys. GTA VI uses RPF9 (`9FPR`, see vi.md).

| Command | What |
|---|---|
| `gtaforge rpf doctor` | ragekit / CodeWalker / 6ixpack paths, key state |
| `gtaforge rpf keys` | derive the game's keys once: ragekit reads the exe, NG tables come from CodeWalker's `magic.dat` (taken from the staged `CodeWalker.Core.dll`). Keys stay in `~/.ragekit/keys`; never commit or ship them |
| `gtaforge rpf info <rpf>` | header of any RPF7 / RPF9 |
| `gtaforge rpf list|find|extract <rpf> [--nested] [--pattern p] [--out dir]` | python for OPEN archives, ragekit for NG |
| `gtaforge rpf pack <folder> --out dlc.rpf` | write an OPEN RPF7 (sorted, deterministic; RSC7 files become resource entries; nested .rpf stored) |
| `gtaforge build` | packs every `<name>.rpf/` folder of a project into `build/` |

Facts behind the reader (ragekit `src/rpf.cpp`, checked against the installed
Enhanced archives): 16-byte entries; directory = name, 0x7FFFFF00, first child,
count; binary = name:16 stored:24 block:24, uncompressed size, encrypted flag
(stored 0 = uncompressed, else raw deflate); resource = bit 31 of byte 7, flags
words for system/graphics pages, a 16-byte header on disk that extraction
rebuilds as `RSC7`. Data sits in 512-byte blocks.

Never edit the game's only copy of an archive. Loose-file loaders (onigiri on
Enhanced) and `mods/` folders avoid touching retail archives at all.
