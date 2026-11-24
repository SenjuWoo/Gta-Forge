# Scripts (asi / SHVDN / Lua)

- C++ asi: `gtaforge new <name> --kind cpp`, `SHV_SDK` -> SDK folder,
  `gtaforge compile`. Script thread: `while(true){ WAIT(0); ... }`.
- SHVDN: `--kind shvdn`, `dotnet build`; reference the matching SHVDN version.
- Lua: `--kind lua` (FiveM/RedM); `gtaforge script lua .` needs luajit.
- `gtaforge script check .` - native names vs the DB, XML well-formed, SDK present.
- `gtaforge natives <name>` - real hash, return, params (subset; full DB linked).