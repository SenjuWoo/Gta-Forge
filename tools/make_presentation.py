#!/usr/bin/env python3
"""Build the README / social images from real runs. Dev-only (needs Pillow, ImageMagick, and for the
asset shots Blender + ragekit + a GTA V install).

  python tools/make_presentation.py            # icon + hero + terminal shots (+ asset shots if inputs exist)
  python tools/make_presentation.py --assets <folder with slot.png table.png>

Terminal shots run the listed gtaforge commands now and draw an excerpt of their JSON: values are
copied from the output, never typed in. The user's home folder is shown as ~ and other machine paths
as <...>. The GTA VI probe runs on a synthetic RPF9 fixture (no GTA VI files exist) and says so.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUT = DOCS / "presentation"
FONTS = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
NIGHT, NIGHT2 = (20, 10, 46), (8, 5, 20)
PINK, GOLD, CYAN, TEXT, DIM = (255, 95, 168), (255, 214, 120), (34, 211, 238), (236, 232, 248), (150, 140, 175)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    for cand in (FONTS / name, Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")):
        if cand.is_file():
            return ImageFont.truetype(str(cand), size)
    return ImageFont.load_default()


def gradient(w: int, h: int, top=NIGHT, bottom=NIGHT2) -> Image.Image:
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return img


def glow_grid(img: Image.Image, horizon: int, alpha: int = 70) -> None:
    w, h = img.size
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for k in range(1, 9):
        y = horizon + int((h - horizon) * (k / 8) ** 1.8)
        d.line([(0, y), (w, y)], fill=CYAN + (alpha,), width=2)
    for k in range(-12, 13):
        d.line([(w // 2, horizon), (w // 2 + k * w // 6, h)], fill=CYAN + (alpha,), width=2)
    d.line([(0, horizon), (w, horizon)], fill=PINK + (200,), width=4)
    img.paste(layer, (0, 0), layer)


def render_icon() -> Path:
    """docs/icon.png from docs/icon.svg (librsvg through ImageMagick)."""
    magick = shutil.which("magick")
    if not magick:
        sys.exit("ImageMagick (magick) not on PATH")
    big = OUT / "_icon1024.png"
    subprocess.run([magick, "-background", "none", "-density", "384", str(DOCS / "icon.svg"), "-resize", "1024x1024", str(big)], check=True)
    Image.open(big).resize((512, 512), Image.LANCZOS).save(DOCS / "icon.png", optimize=True)
    return big


def hero(icon1024: Path, out: Path, w: int, h: int) -> None:
    """Title card. 2:1 at 1280x640 for the GitHub social preview; 16:9 for the README cover.
    The 1280x640 layout is centered on the canvas; the grid and glow fill the rest."""
    dx, dy = (w - 1280) // 2, (h - 640) // 2
    img = gradient(w, h)
    sun = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sun).ellipse([760 + dx, 70 + dy, 1240 + dx, 550 + dy], fill=(255, 46, 136, 70))
    sun = sun.filter(ImageFilter.GaussianBlur(90))
    img.paste(sun, (0, 0), sun)
    glow_grid(img, 566 + dy, 45)
    icon = Image.open(icon1024).convert("RGBA").resize((360, 360), Image.LANCZOS)
    shadow = Image.new("RGBA", (440, 440), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([40, 50, 400, 410], radius=80, fill=(0, 0, 0, 160))
    shadow = shadow.filter(ImageFilter.GaussianBlur(22))
    img.paste(shadow, (60 + dx, 100 + dy), shadow)
    img.paste(icon, (100 + dx, 140 + dy), icon)
    d = ImageDraw.Draw(img)
    d.text((520 + dx, 168 + dy), "GTA Forge", font=font("segoeuib.ttf", 104), fill=TEXT)
    d.text((526 + dx, 300 + dy), "Make, check and ship GTA V mods against", font=font("segoeuisl.ttf", 36), fill=TEXT)
    d.text((526 + dx, 346 + dy), "the game you actually have installed.", font=font("segoeuisl.ttf", 36), fill=TEXT)
    d.text((526 + dx, 414 + dy), "Ready for the first GTA VI files.", font=font("segoeuib.ttf", 34), fill=GOLD)
    x = 526 + dx
    f = font("segoeuib.ttf", 22)
    for c in ("RPF7 + RPF9", "asset index", "real builds", "GTA VI kit"):
        tw = d.textlength(c, font=f)
        d.rounded_rectangle([x, 486 + dy, x + tw + 32, 526 + dy], radius=20, outline=CYAN, width=2, fill=(10, 8, 24))
        d.text((x + 16, 491 + dy), c, font=f, fill=CYAN)
        x += tw + 46
    img.save(out, optimize=True)


# ---------- terminal shots from real runs ----------

def gtaforge(*args: str, cwd: Path | None = None) -> tuple[int, dict]:
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    r = subprocess.run([sys.executable, "-m", "gtaforge", *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, cwd=cwd)
    return r.returncode, json.loads(r.stdout)


def redact(text: str) -> str:
    home = str(Path.home())
    text = text.replace(home, "~").replace(home.replace("\\", "/"), "~")
    text = re.sub(r"[A-Za-z]:\\\\?[^\s\"']*?\\(gtaforge_[a-z]+_[A-Za-z0-9_]+|tmp[A-Za-z0-9_]+)", r"<tmp>", text)
    text = re.sub(r"[A-Za-z]:[\\/][^\s\"',]*Grand Theft Auto V Enhanced", "<GTA V Enhanced>", text)
    return text


def ell(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n // 2 - 2] + " … " + s[-(n // 2 - 2):]


def terminal(name: str, title: str, blocks: list[tuple[str, list[tuple[str, str]]]], caption: str) -> None:
    mono, monob = font("CascadiaMono.ttf", 22), font("consolab.ttf", 22)
    lh, pad, width = 34, 36, 1400
    def wrapped(k: str, v: str) -> list[str]:
        room = 94 - len(k)
        import textwrap
        parts = textwrap.wrap(redact(v), room, break_long_words=True, break_on_hyphens=False) or [""]
        if len(parts) > 3:
            parts = parts[:3]
            parts[-1] = parts[-1][: room - 2] + " …"
        return parts

    lines = sum(1 + sum(len(wrapped(k, v)) for k, v in kv) + 1 for _c, kv in blocks)
    h = 70 + pad + lines * lh + 70
    img = gradient(width, h, (16, 10, 32), (8, 6, 16))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, width - 1, h - 1], radius=18, outline=(60, 40, 90), width=2)
    d.rectangle([2, 2, width - 3, 52], fill=(28, 20, 48))
    for i, c in enumerate(((255, 95, 87), (254, 188, 46), (40, 200, 64))):
        d.ellipse([22 + i * 30, 18, 38 + i * 30, 34], fill=c)
    d.text((width // 2 - d.textlength(title, font=mono) // 2, 14), title, font=mono, fill=DIM)
    y = 70 + pad // 2
    for cmd, kv in blocks:
        d.text((pad, y), "$", font=monob, fill=PINK)
        d.text((pad + 28, y), redact(cmd), font=monob, fill=CYAN)
        y += lh
        for k, v in kv:
            d.text((pad + 28, y), k, font=mono, fill=GOLD)
            for part in wrapped(k, v):
                d.text((pad + 28 + d.textlength(k + " ", font=mono), y), part, font=mono, fill=TEXT)
                y += lh
        y += lh
    d.text((pad, h - 52), caption, font=font("segoeuii.ttf", 21), fill=DIM)
    img.save(OUT / name, optimize=True)


def shots() -> None:
    dealer = "anim_casino_b@amb@casino@games@blackjack@dealer"
    _c, doc = gtaforge("doctor")
    g = doc.get("game", {})
    gv = g.get("version", {})
    _c, find = gtaforge("find", dealer, "--ext", ".ycd")
    _c, clips = gtaforge("anim", "clips", "--dict", dealer)
    _c, nat = gtaforge("natives", "TASK_PLAY_ANIM", "--limit", "1")
    terminal("screenshot-doctor-find.png", "confirm names against the installed game", [
        ("gtaforge doctor", [("game:", f"{gv.get('edition')} {gv.get('file_version')} ({g.get('status')})"),
                             ("hook:", f"ScriptHookV supports {', '.join(gv.get('shv_supports', []))}; this build: "
                                       f"{'yes' if gv.get('shv_supported') else 'no (doctor warns)'}"),
                             ("index:", f"{doc.get('index', {}).get('entries', 0):,} archive entries"),
                             ("build:", "cpp ready" if doc.get("build", {}).get("cpp_ready") else "cpp not ready")]),
        (f"gtaforge find {dealer} --ext .ycd", [("found:", str(find.get("found")).lower()),
                                                ("where:", (find.get("exact") or [{}])[0].get("path", "-"))]),
        (f"gtaforge anim clips --dict {dealer}", [("clips:", f"{clips.get('clip_count')} of {clips.get('declared')} declared"),
                                                  ("sample:", ", ".join(clips.get("clips", [])[:4]))]),
        ("gtaforge natives TASK_PLAY_ANIM", [("sig:", (nat.get("exact") or {}).get("signature", "-"))]),
    ], "Real output, excerpted. Every name above came out of the local GTA V Enhanced install or the native DB.")

    tmp = Path(tempfile.mkdtemp(prefix="gtaforge_pres_"))
    try:
        p = tmp / "NeonNights"
        _c, new = gtaforge("new", "NeonNights", "--folder", str(p), "--kind", "cpp", "--kind", "menyoo", "--target-game", "enhanced")
        _c, chk = gtaforge("check", "--compile", "--project", str(p))
        comp = (chk.get("compile") or {}).get("results", [{}])[0]
        _c, pkg = gtaforge("package", "--project", str(p))
        _c, val = gtaforge("validate", pkg.get("archive", ""))
        ev = chk.get("evidence", {})
        terminal("screenshot-build.png", "a ScriptHookV asi, built and packaged", [
            ("gtaforge new NeonNights --kind cpp --kind menyoo --target-game enhanced", [("files:", ", ".join(new.get("files", [])))]),
            ("gtaforge check --compile", [("natives:", f"{chk.get('native_calls')} calls checked (name, namespace, arg count)"),
                                          ("compile:", f"{comp.get('evidence', {}).get('compile')} via {comp.get('generator')} -> {', '.join(comp.get('outputs', []))}"),
                                          ("evidence:", " | ".join(f"{k} {v}" for k, v in ev.items()))]),
            ("gtaforge package && gtaforge validate artifacts/NeonNights-0.1.0.zip", [("zip:", ", ".join(pkg.get("names", []))),
                                                                                       ("problems:", str(len(val.get("problems", []))))]),
        ], "Real run on this machine: MSVC found with vswhere, the SDK template compiles, the zip holds only the payload.")

        dump = tmp / "dump"
        (dump / "x64").mkdir(parents=True)
        hdr = bytearray(0x40)
        hdr[0:4] = b"9FPR"
        struct.pack_into("<IIIQ", hdr, 4, 0x40 + 96, 0x40 + 64, 0x20, 0x5EED)
        struct.pack_into("<I", hdr, 0x24, 4)
        data = bytearray(0x2000)
        data[0:0x40] = hdr
        data[0x1000:0x1040] = hdr
        (dump / "x64" / "a.rpf").write_bytes(bytes(data))
        (dump / "GTA6.exe").write_bytes(b"MZ" + b"\0" * 64)
        _c, pr = gtaforge("vi", "probe", str(dump), "--out", str(tmp / "p.json"))
        _c, w = gtaforge("vi", "watch")
        _c, cl = gtaforge("vi", "checklist", str(dump))
        done = [c["check"] for c in cl.get("checks", []) if c["status"] == "done"]
        ready = [c["check"] for c in cl.get("checks", []) if c["status"] == "ready"]
        rows = {r["repo"].split("/")[-1]: r for r in w.get("repos", [])}
        terminal("screenshot-vi-kit.png", "GTA VI day-one kit", [
            ("gtaforge vi probe <dump>", [("archives:", json.dumps(pr.get("archives", {}).get("by_format"))),
                                          ("rpf9:", f"{pr['archives']['items'][0]['header']['records']} records, nested {pr['archives']['items'][0].get('nested')}"),
                                          ("verdict:", pr.get("verdict", ""))]),
            ("gtaforge vi watch", [(f"{k}:", f"{rows[k]['status']} {rows[k].get('pushed_at') or ''}") for k in ("VIctory", "6to5m", "RageForge") if k in rows]),
            ("gtaforge vi checklist <folder>", [("checks:", f"{len(cl.get('checks', []))}: done {', '.join(done)}; ready {', '.join(ready)}")]),
        ], "vi probe ran on a synthetic RPF9 fixture (no GTA VI files exist yet); vi watch is live GitHub data.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def assets(folder: Path) -> None:
    w, h = 1600, 820
    img = gradient(w, h)
    glow_grid(img, 650, 35)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 680, w, h], fill=(8, 6, 18))
    for i, (fn, label) in enumerate((("slot.png", "vw_prop_casino_slot_01a  (.ydr + .ytd)"),
                                     ("table.png", "h4_prop_casino_blckjack_01a  (.ydr)"))):
        src = folder / fn
        if not src.is_file():
            sys.exit(f"missing {src}")
        im = Image.open(src).convert("RGBA")
        im = im.crop(im.getchannel("A").getbbox())  # trim the empty render margin
        scale = min(640 / im.width, 560 / im.height)
        im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
        cx = 400 + i * 800
        img.paste(im, (cx - im.width // 2, 650 - im.height), im)  # stand on the horizon line
        tw = d.textlength(label, font=font("CascadiaMono.ttf", 24))
        d.text((cx - tw / 2, 700), label, font=font("CascadiaMono.ttf", 24), fill=TEXT)
    cap = "Pulled from a local GTA V Enhanced install: gtaforge find -> ragekit rpf cat -> ragekit gltf -> Blender render"
    d.text((w / 2 - d.textlength(cap, font=font("segoeuii.ttf", 24)) / 2, 774), cap, font=font("segoeuii.ttf", 24), fill=DIM)
    img.save(OUT / "asset-pipeline.png", optimize=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--assets", help="folder with slot.png and table.png renders (tools/render_glb.py)")
    ap.add_argument("--skip-shots", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    big = render_icon()
    hero(big, OUT / "hero.png", 1600, 900)
    hero(big, OUT / "social-preview.png", 1280, 640)
    big.unlink()
    if not a.skip_shots:
        shots()
    if a.assets:
        assets(Path(a.assets))
    for p in sorted(OUT.glob("*.png")):
        print(p.relative_to(ROOT), Image.open(p).size, p.stat().st_size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
