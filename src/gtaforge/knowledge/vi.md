# GTA VI: the day-one kit

No PC-runnable GTA VI build exists yet (console launch 2026-11-19). The kit
below runs today on any folder and is tested on synthetic RPF9 files and on the
GTA V install as a control, so the first real files meet working tools.

| Command | Day one |
|---|---|
| `gtaforge vi status` | platform + community tool watch (knowledge/vi.json) |
| `gtaforge vi probe <folder>` | census by content signature: executables (version, sha256), RPF7/8/9 archives with RPF9 header fields and nested-archive count, AWC, TTPF pools, PSO, DDS...; report JSON in `<forge home>/vi/` |
| `gtaforge vi checklist <folder>` | the 12 first checks, done where a tool can (build record, archive census, explorer readiness), the rest as exact next commands |
| `gtaforge vi extract <rpf> [--list] --out <empty dir>` | 6ixpack (6to5m) extraction / listing |
| `gtaforge vi names <hashes> --words <list>` | name recovery: joaat over wordlists + the GTA V asset index + generated variants (`_hi`, `_lod`, `_g9ec`, ...), matched against a text or raw u32 hash table |
| `gtaforge vi build-6to5m` | rebuild 6ixpack from vendor/6to5m-main |

RPF9 header (6to5m container.rs): `9FPR`, len, split, trailer, u64 id, files at
0x24; two 16-byte-record tables (encrypted); nested archives on 0x1000 sectors.

A mod needs (1) a PC-runnable build the owner supplies, (2) a script/native
dispatch, (3) an archive tool. Until then build engine-agnostic code against
GTA V and keep content names in binding tables (bindings.md). Any "GTA VI PC"
installer is fake or malware.
