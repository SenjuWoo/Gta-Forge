# Asset index: confirm a name before you use it

`gtaforge index build` lists every entry of every archive of the installed game
(nested archives included) through ragekit and writes
`<forge home>/index/<edition>-<version>.tsv.gz`. On Enhanced 1.0.1158.16 that is
123 archives and about 389,000 entries in a few seconds (needs `gtaforge rpf keys` once).

`gtaforge find <name>` answers "does this exist, and where":

- anim dicts are clip dictionaries: `mini@strip_club@idles@stripper.ycd`
- models: `.ydr` (drawable), `.yft` (fragment: vehicles, breakables), `.ydd` (ped parts)
- textures: `.ytd`; placements: `.ymap`; archetypes: `.ytyp`; audio: `.awc`

`--ext .ycd` narrows the type. Exit 1 means nothing matched: the name is wrong
or the content is not in this build. Rebuild the index after a game patch
(the file name carries the exe version).

Clip names inside a dictionary are not in the archive listing; use the anim
index (`gtaforge menyoo index` from Menyoo's PedAnimList.txt) for clips.
