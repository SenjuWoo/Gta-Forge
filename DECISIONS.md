# Decisions

- **GTA V first, GTA VI later.** No playable VI PC build; the forge watches VI
  (RPF9 index, 6to5m) and never claims VI support.
- **Python CLI, no MCP by default.** Works in a fresh shell; JSON + exit codes.
- **Facts as data with tiers.** Natives subset is real (fivem natives.json);
  asset names must be confirmed, never invented.
- **Single-player only.** No GTA Online, no uploads, no game launch.
- **Vendored sources are git-ignored** (6to5m, ragekit, awesome index); the
  forge references them, it does not redistribute them.