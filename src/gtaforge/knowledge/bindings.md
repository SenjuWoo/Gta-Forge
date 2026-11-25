# Binding tables

Code names a *content key* (`casino.blackjack.dealer_idle`); a per-game table
says which asset fills it. Porting a mod from GTA V to GTA VI is then filling a
new table, and coverage is measurable.

Keys file:

```json
{"keys": {"casino.blackjack.dealer_idle": {"module": "casino", "type": "anim", "required": true}}}
```

Per-game table:

```json
{"game": "gta5", "bindings": {
  "casino.blackjack.dealer_idle": {"dict": "anim_casino_b@amb@casino@games@blackjack@dealer", "clip": "idle"},
  "casino.table": {"model": "vw_prop_casino_blckjack_01"},
  "life.sports_car": "adder",
  "adult.some_scene": null}}
```

`null` = known missing in this game: the feature degrades, the mod does not.

`gtaforge bindings <keys.json> <table.json>` checks every key: unbound,
declared-missing, asset not in game (asset index), clip not in anim index, or
verified. Coverage is reported per module; exit 1 when a required key fails or
a bound asset does not exist. Types: anim, model, prop, ped, vehicle, texture,
interior, audio, map, any.
