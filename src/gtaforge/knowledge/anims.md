# Animations

- Dict exists? `gtaforge find <dict> --ext .ycd` (asset index of the installed game).
- Clips from the game itself: `gtaforge anim clips --dict <dict>` (ragekit reads the .ycd), or for a
  list `gtaforge anim build --batch dicts.txt`; lookups then use that game clip index.
- Clips of a dict: `gtaforge anim --dict <dict> [--clip <part>]` from an anim
  index built with `gtaforge menyoo index --folder <menyooStuff>` (PedAnimList.txt),
  or any folder of `{dict: [clips]}` JSON set as `GTA_FORGE_ANIM_INDEX`.
- Play: `STREAMING::REQUEST_ANIM_DICT` -> wait for `HAS_ANIM_DICT_LOADED` ->
  `TASK::TASK_PLAY_ANIM` -> `REMOVE_ANIM_DICT` when done.
- Confirmed in Enhanced 1.0.1158.16 (index): `mini@strip_club@idles@stripper`,
  `mini@prostitutes@sexnorm_veh` (x64c.rpf clip_mini@), casino dealer
  `anim_casino_b@amb@casino@games@blackjack@dealer` (mpvinewood dlc).
  Adult dict families: `mini@prostitutes@*`, `mini@strip_club@*`. Adult
  characters only; a character recorded as under 18 is never a participant.
- GTA VI clips: unknown until the files are readable; never reuse a V name as a VI fact.
