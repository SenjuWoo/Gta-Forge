# Third-party

- Native data: alloc8or/gta5-nativedb-data `natives.json` @ 424fb51 (2026-09-15), shipped as
  `knowledge/natives.json.gz` (names, hashes, signatures; comments truncated).
- ScriptHookV / SDK: dev-c.com, freeware, redistribution not allowed (link only; never in a package).
- ScriptHookVDotNet: github.com/scripthookvdotnet/scripthookvdotnet (referenced at build time, not shipped).
- CodeWalker (crxhvrd continuation): no licence file; private use. The forge reads its embedded
  magic.dat on the user's machine; nothing from it is redistributed.
- ragekit: NOASSERTION; 6to5m: GPL-3.0; awesome-gta6-RE index: CC0-1.0. Used as local tools.
- Microsoft.NETFramework.ReferenceAssemblies (NuGet, MIT): build-time only, in the SHVDN template.
Vendored copies live in vendor/ (git-ignored) and are not shipped.
