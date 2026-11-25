# Contributing to GTA Forge

Thanks for helping. The bar is simple: **a claim needs evidence, and a fix needs a test.**

## Setup

```bash
git clone https://github.com/SenjuWoo/Gta-Forge
cd Gta-Forge
python -m pip install -e .
python tests/run_tests.py
```

The offline tests need nothing but Python. The tests in `tests/test_real.py`
run against a local GTA V install and toolchain and skip themselves when those
are absent. If you have the game, run them before a pull request that touches
archives, the index, builds or deploy.

## Rules of the house

- **Start with a failing test.** Bugs get a regression test in `tests/test_gtaforge.py`
  (offline) or `tests/test_real.py` (needs the game or tools).
- **Facts need a primary source.** File formats, hashes and native signatures come
  from upstream code (ragekit, 6to5m, the native DB) or from the installed files,
  cited in the module docstring or in `knowledge/*.json` with a `source`.
- **Bad input is exit 1 or 2 with a `fix`, never a traceback.** The fuzz test runs
  every command with nonsense and fails on exit 3.
- **Standard library only** at runtime. Dev tools (Pillow for the README images)
  stay out of `pyproject.toml` dependencies.
- **Single-player only.** No GTA Online features, no uploads, no game launch.
- **No machine paths in the repo.** Personal tool locations belong in
  `%LOCALAPPDATA%\GTAForge\config.json`.
- **Version bumps** touch `src/gtaforge/__init__.py`, `CHANGELOG.md`, `STATE.md`,
  `README.md` and `skills/gta-forge/SKILL.md` together (a test checks them).

## README images

`python tools/make_presentation.py --assets <renders>` rebuilds everything under
`docs/presentation/` from real command runs. The terminal shots copy values from
the JSON output. Render props with `blender -b -P tools/render_glb.py -- <in.glb> <out.png>`.

## Reporting a bug

Open an issue with the output of `gtaforge doctor` and the failing command's
JSON. Before you paste them, replace your user folder with `~`.
