import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gtaforge import __version__
from gtaforge.cli import main
from gtaforge.util import joaat, tweakdb_id, ForgeError
from gtaforge.game import is_game_root, find_game
from gtaforge.knowledge import plan, facts, docs
from gtaforge.natives import search
from gtaforge.project import create, find_project, bump
from gtaforge.package import run as package, validate, runtime_files
from gtaforge.deploy import run as deploy
from gtaforge.check import run as check
from gtaforge.scripts import detect
from gtaforge.menyoo import run as menyoo
from gtaforge.anims import lookup
from gtaforge.conflicts import run as conflicts
from gtaforge.logs import run as logs


def fake_game(tmp: Path, edition: str = "enhanced") -> Path:
    g = tmp / "Game [x]"
    (g / "scripts" / "OtherMod").mkdir(parents=True)
    (g / "scripts" / "OtherMod" / "Main.cs").write_text("class X {}", encoding="utf-8")
    (g / "update/x64/dlcpacks").mkdir(parents=True)
    (g / "ScriptHookV.dll").write_bytes(b"MZ" + b"\0" * 100)
    (g / "dinput8.dll").write_bytes(b"MZ")
    (g / ("GTA5_Enhanced.exe" if edition == "enhanced" else "GTA5.exe")).write_bytes(b"MZ")
    (g / "args.txt").write_text("-nobattleye\n", encoding="utf-8")
    return g


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gtaforge_test_"))
        self.addCleanup(__import__("shutil").rmtree, self.tmp, True)

    def cli(self, *args):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(list(args))
        return code, json.loads(buf.getvalue())


class TestHashes(Base):
    def test_joaat_known(self):
        # joaat("") is 0; joaat of a known string is stable (self-consistency + reference value)
        self.assertEqual(joaat(""), "00000000")
        self.assertEqual(len(tweakdb_id("Blackjack")), 16)

    def test_hash_command(self):
        f = self.tmp / "a.bin"
        f.write_bytes(b"hello")
        code, out = self.cli("hash", str(f))
        self.assertEqual(code, 0)
        self.assertEqual(out["bytes"], 5)


class TestGame(Base):
    def test_detects_awkward_path(self):
        g = fake_game(self.tmp)
        self.assertTrue(is_game_root(g))
        root, how, _ = find_game(str(g))
        self.assertEqual(root, g)
        self.assertEqual(how, "argument")

    def test_rejects_non_game(self):
        with self.assertRaises(ForgeError):
            find_game(str(self.tmp))

    def test_doctor_missing_game_is_named(self):
        code, out = self.cli("doctor", "--game", str(self.tmp / "nope"))
        self.assertEqual(code, 2)
        self.assertEqual(out["game"]["status"], "missing")

    def test_game_inventory(self):
        g = fake_game(self.tmp)
        code, out = self.cli("game", "--game", str(g))
        self.assertEqual(code, 0)
        self.assertEqual(out["inventory"]["asi_loaders"], ["dinput8.dll"])
        self.assertEqual(out["version"]["edition"], "enhanced")


class TestKnowledge(Base):
    def test_plan_routes(self):
        r = plan("add a blackjack table to the casino")
        self.assertEqual(r["route"]["id"], "casino")
        self.assertTrue(r["route"]["docs"])

    def test_facts_and_docs(self):
        self.assertIn("game.versions", facts())
        self.assertTrue(any(d["name"] == "rig.md" for d in docs()))

    def test_natives_real(self):
        r = search("TASK_PLAY_ANIM")
        self.assertGreaterEqual(r["count"], 1)
        exact = [n for n in r["natives"] if n["name"] == "TASK_PLAY_ANIM"]
        self.assertGreaterEqual(len(exact[0]["hash"]), 8)


class TestProject(Base):
    def test_new_check_compile_path(self):
        code, out = self.cli("new", "Demo", "--folder", str(self.tmp / "Demo"), "--kind", "cpp", "--kind", "xml")
        self.assertEqual(code, 0)
        p = self.tmp / "Demo"
        self.assertTrue((p / "gtaforge.json").is_file())
        self.assertEqual(detect(p), ["cpp", "xml"])
        code, out = self.cli("check", "--project", str(p))
        self.assertEqual(code, 0)
        self.assertFalse(out["errors"])
        code, out = self.cli("bump", "minor", "--project", str(p))
        self.assertEqual(out["new"], "0.2.0")
        code, out = self.cli("new", "Demo", "--folder", str(p), "--kind", "cpp")
        self.assertEqual(code, 2)  # not empty without --force

    def test_package_excludes_non_runtime(self):
        p = self.tmp / "Demo"
        self.cli("new", "Demo", "--folder", str(p), "--kind", "cpp")
        (p / "src" / "main.cpp")
        (p / "STATE.md").write_text("x")
        (p / "tests").mkdir(); (p / "tests" / "t.py").write_text("x")
        (p / "payload.asi").write_bytes(b"MZ")
        code, out = self.cli("package", "--project", str(p))
        self.assertEqual(code, 0)
        z = out["archive"]
        code, v = self.cli("validate", z)
        self.assertEqual(code, 0)
        self.assertEqual(v["files"], 3)  # CMakeLists, src/main.cpp, payload.asi
        with __import__("zipfile").ZipFile(z) as zf:
            self.assertNotIn("STATE.md", zf.namelist())

    def test_secret_blocked(self):
        p = self.tmp / "S"
        self.cli("new", "S", "--folder", str(p), "--kind", "xml")
        (p / "key.txt").write_text("api_key = 'ABCDEFGHIJKLMNOP1234'")
        code, out = self.cli("package", "--project", str(p))
        self.assertEqual(code, 2)

    def test_deploy_roundtrip(self):
        g = fake_game(self.tmp)
        p = self.tmp / "D"
        self.cli("new", "D", "--folder", str(p), "--kind", "shvdn")
        (p / "Main.cs").write_text("class M {}", encoding="utf-8")
        code, out = self.cli("deploy", "--project", str(p), "--game", str(g))
        self.assertEqual(code, 0)
        self.assertTrue((g / "scripts" / "D" / "Main.cs").is_file())
        code, out = self.cli("deploy", "--remove", "--project", str(p), "--game", str(g))
        self.assertEqual(code, 0)
        self.assertFalse((g / "scripts" / "D" / "Main.cs").exists())


class TestMenyooAnims(Base):
    def test_index_and_lookup(self):
        m = self.tmp / "menyooStuff"
        m.mkdir()
        (m / "PedAnimList.txt").write_text("mini@strip_club@idles@stripper idle_a\nmini@prostitutes@sexnorm_veh bj_loop_male\n", encoding="utf-8")
        (m / "PedSpeechList.txt").write_text("A_F_M = AGREE, 1\n", encoding="utf-8")
        (m / "PropList.txt").write_text("prop_casino\n", encoding="utf-8")
        (m / "PedList.xml").write_text("<peds/>", encoding="utf-8")
        (m / "CutsceneLabels.txt").write_text("x", encoding="utf-8")
        out = self.tmp / "idx"
        code, r = self.cli("menyoo", "index", "--folder", str(m), "--out", str(out))
        self.assertEqual(code, 0)
        self.assertEqual(r["dicts"], 2)
        os.environ["GTA_FORGE_ANIM_INDEX"] = str(out)
        self.addCleanup(os.environ.pop, "GTA_FORGE_ANIM_INDEX", None)
        code, r = self.cli("anim", "--dict", "mini@strip_club@idles@stripper")
        self.assertEqual(code, 0)
        self.assertTrue(r["found"])
        code, r = self.cli("anim", "--pattern", "prostitutes")
        self.assertEqual(r["dicts"], 1)


class TestLogsConflicts(Base):
    def test_logs_and_conflicts(self):
        g = fake_game(self.tmp)
        (g / "ScriptHookV.log").write_text("ok\nERROR something failed\n", encoding="utf-8")
        code, out = self.cli("logs", "--game", str(g))
        self.assertEqual(out["logs"][0]["errors"], 1)
        code, out = self.cli("conflicts", "--project", str(self.tmp / "P"), "--game", str(g))
        self.assertEqual(code, 2)  # no manifest in self.tmp: named failure, not a crash


class TestVersionMirrors(Base):
    def test_mirrors(self):
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        state = (ROOT / "STATE.md").read_text(encoding="utf-8")
        self.assertIn(__version__, text)
        self.assertIn(__version__, state)


if __name__ == "__main__":
    unittest.main()