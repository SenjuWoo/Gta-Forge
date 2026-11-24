# Deploy and logs

- `gtaforge deploy` copies the runtime files into the game (scripts/<name> for
  SHVDN/Lua, game root for asi/xml) with a receipt and backups.
- `gtaforge deploy --remove` restores from the receipt.
- Launch with `-nobattleye`; then `gtaforge logs --mod <name>`.
- Deploy is explicit; the forge never launches the game or publishes.