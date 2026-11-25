# Decisions

- **GTA V first, GTA VI kit now.** No playable VI PC build; the forge ships tools
  that run today on any folder (probe, checklist, names, extract, watch) and never
  claims VI mod support.
- **Python CLI, stdlib only, no MCP by default.** Works in a fresh shell; JSON + exit codes.
- **Facts as data with tiers.** Native DB is the full alloc8or set; asset names are
  confirmed in the installed game's index, never invented.
- **Pure-Python RPF7 for OPEN archives, ragekit for NG.** NG needs the game's keys and
  272 tables; ragekit already implements it and builds here. Keys are derived on the
  user's machine from their exe + CodeWalker's magic.dat and never committed or shipped.
- **Payload allowlist, not a denylist.** gtaforge.json says what ships (build outputs,
  data); package and deploy never walk the source tree.
- **Build in `<project>/build` with captured vcvars.** Outputs are the payload; a plain
  shell works without a developer prompt.
- **Generated natives.h with its own variadic invoker.** The SDK's natives.h is from
  2016 and its caller stops at 25 arguments; natives take up to 32.
- **Single-player only.** No GTA Online, no uploads, no game launch.
- **Vendored sources are git-ignored** (6to5m, ragekit, awesome index); referenced, not redistributed.
