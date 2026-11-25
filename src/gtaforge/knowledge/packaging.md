# Packaging and release

- `gtaforge bump patch|minor|major` - manifest, CHANGELOG heading, csproj Version.
- `gtaforge package` - zip of the payload laid out like the game folder
  (extract into the game = install), fixed timestamps (same input, same bytes),
  receipt with every file's sha256.
- `gtaforge validate <zip>` - fails on sources/notes/build junk, paths that
  escape the folder, framework files (ScriptHookV.dll, dinput8.dll, SHVDN:
  link them, do not redistribute), and secrets.
- `gtaforge nexus` - description + changelog BBCode; no upload.
- Public text: no personal names or machine paths; state the game edition,
  patch and ScriptHookV version the build needs. Story mode only.
