# Deploy and test

- `gtaforge deploy --dry-run` shows every file and where it goes.
- `gtaforge deploy` copies the **payload** (gtaforge.json `payload` rules: build
  outputs and data, never sources) into the game, each file by temp copy +
  rename, with a receipt in `<forge home>/deploy/<name>.json`.
- The first time a game file is replaced, its original is backed up; later
  deploys keep that original. Files dropped from the payload are taken out.
- `gtaforge deploy --remove` restores originals, deletes what the forge added,
  leaves files someone changed after the deploy, prunes empty folders.
- Launch story mode with `-nobattleye` (args.txt), then `gtaforge logs --mod <name>`.
- The forge never launches the game, never touches GTA Online, never publishes.
