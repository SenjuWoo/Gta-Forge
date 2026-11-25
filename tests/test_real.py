"""Real-install and real-toolchain tests. Each skips (with the reason) when its game, tool or key is absent,
so CI stays green while a dev machine proves the forge against the real thing.

Set GTA_FORGE_REAL=0 to skip all of them.
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gtaforge.cli import main
from gtaforge.game import find_game
from gtaforge.util import find_tool, joaat, msvc_install

OFF = os.environ.get("GTA_FORGE_REAL") == "0"
GAME = None if OFF else find_game(None)[0]


def cli(*args):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main([str(a) for a in args])
    return code, json.loads(buf.getvalue())


def keys_ok() -> bool:
    from gtaforge.rpf import keys_state
    return keys_state()["ng"]


def index_ok() -> bool:
    from gtaforge.util import ForgeError
    try:
        from gtaforge.index import current_index
        current_index(GAME)
        return True
    except ForgeError:
        return False


@unittest.skipIf(GAME is None, "no GTA V install found")
class TestRealGame(unittest.TestCase):
    def test_every_top_level_archive_is_rpf7(self):
        from gtaforge import rpf7
        arcs = sorted(GAME.glob("*.rpf")) + sorted((GAME / "update").glob("*.rpf"))
        self.assertGreater(len(arcs), 5)
        for a in arcs:
            h = rpf7.read_header(a)
            self.assertEqual(h["format"], "rpf7", a)
            self.assertIn(h["encryption"], ("ng", "aes", "open", "none"), a)

    def test_doctor_reads_the_install(self):
        code, out = cli("doctor", "--game", GAME)
        self.assertIn(code, (0, 1))
        self.assertIn(out["game"]["version"]["edition"], ("enhanced", "legacy"))
        self.assertTrue(out["game"]["version"]["file_version"])

    @unittest.skipUnless(find_tool("ragekit") and keys_ok(), "ragekit or NG keys missing (gtaforge rpf keys)")
    def test_ragekit_lists_retail_archive(self):
        code, out = cli("rpf", "list", GAME / "common.rpf", "--limit", "5")
        self.assertEqual((code, out["engine"], out["encryption"]), (0, "ragekit", "ng"))
        self.assertGreater(out["entries"], 100)

    @unittest.skipUnless(find_tool("ragekit") and keys_ok(), "ragekit or NG keys missing")
    def test_ragekit_extract_one_file(self):
        tmp = Path(tempfile.mkdtemp(prefix="gtaforge_real_"))
        self.addCleanup(shutil.rmtree, tmp, True)
        code, out = cli("rpf", "extract", GAME / "common.rpf", "--pattern", "data/action/branches.meta", "--out", tmp)
        self.assertEqual(code, 0, out)
        f = tmp / "data" / "action" / "branches.meta"
        self.assertTrue(f.is_file())
        self.assertIn(b"<", f.read_bytes()[:200])

    @unittest.skipUnless(index_ok(), "no asset index (gtaforge index build)")
    def test_index_confirms_known_assets(self):
        for name, ext in (("mini@strip_club@idles@stripper", ".ycd"), ("mini@prostitutes@sexnorm_veh", ".ycd"),
                          ("anim_casino_b@amb@casino@games@blackjack@dealer", ".ycd"), ("adder", ".yft"),
                          ("prop_bench_01a", None)):
            code, out = cli("find", name, *(["--ext", ext] if ext else []))
            self.assertTrue(out["found"], name)
        code, out = cli("find", "definitely_not_a_gta_asset_name_42")
        self.assertEqual(code, 1)

    def test_vi_probe_on_gta5_control(self):
        tmp = Path(tempfile.mkdtemp(prefix="gtaforge_real_"))
        self.addCleanup(shutil.rmtree, tmp, True)
        from gtaforge.vi import probe
        r = probe(GAME, out=tmp / "p.json", hash_exes=False, nested=False)
        self.assertGreater(r["archives"]["by_format"].get("rpf7", 0), 10)
        self.assertNotIn("rpf9", r["archives"]["by_format"])
        self.assertTrue(any(e["looks_like_title"] for e in r["executables"]))
        self.assertIn("RPF7", r["verdict"])

    @unittest.skipUnless(index_ok(), "no asset index")
    def test_vi_names_recovers_real_gta5_hashes(self):
        """Control for day one: hash 2,000 real model names, recover them from the index as dictionary."""
        from gtaforge.index import _load, current_index
        rows, stems = _load(str(current_index(GAME)))
        names = sorted({p.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower() for p, _k, _s in rows if p.endswith(".ydr")})[:2000]
        tmp = Path(tempfile.mkdtemp(prefix="gtaforge_real_"))
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "h.txt").write_text("\n".join("0x" + joaat(n) for n in names), encoding="utf-8")
        code, out = cli("vi", "names", tmp / "h.txt")
        self.assertEqual(code, 0)
        self.assertGreaterEqual(out["rate"], 0.99)


SDK = find_tool("shv_sdk")


@unittest.skipUnless(not OFF and SDK and msvc_install() and find_tool("cmake"), "MSVC, CMake or ScriptHookV SDK missing")
class TestRealCompile(unittest.TestCase):
    def test_cpp_template_builds_an_asi_importing_scripthookv(self):
        tmp = Path(tempfile.mkdtemp(prefix="gtaforge_real_"))
        self.addCleanup(shutil.rmtree, tmp, True)
        cli("new", "RealAsi", "--folder", tmp / "RealAsi", "--kind", "cpp")
        code, out = cli("check", "--compile", "--project", tmp / "RealAsi")
        self.assertEqual(code, 0, json.dumps(out)[-3000:])
        asi = tmp / "RealAsi" / "build" / "RealAsi.asi"
        data = asi.read_bytes()
        self.assertEqual(data[:2], b"MZ")
        self.assertIn(b"ScriptHookV.dll", data)
        self.assertIn(b"scriptRegister", data)

    @unittest.skipUnless(find_tool("dotnet") and find_tool("shvdn_ref"), "dotnet or ScriptHookVDotNet3.dll missing")
    def test_shvdn_template_builds(self):
        tmp = Path(tempfile.mkdtemp(prefix="gtaforge_real_"))
        self.addCleanup(shutil.rmtree, tmp, True)
        cli("new", "RealNet", "--folder", tmp / "RealNet", "--kind", "shvdn")
        code, out = cli("compile", "--project", tmp / "RealNet")
        self.assertEqual(code, 0, json.dumps(out)[-3000:])
        self.assertTrue((tmp / "RealNet" / "bin" / "Release" / "RealNet.dll").is_file())


if __name__ == "__main__":
    unittest.main()
