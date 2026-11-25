"""Offline suite (fake game trees, synthetic archives). Real-install / real-toolchain tests live in
test_real.py and skip themselves when the game or the tools are absent."""
import gzip
import io
import json
import os
import shutil
import struct
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gtaforge import __version__, rpf7, rpf9
from gtaforge.cli import main, parser
from gtaforge.util import ForgeError, joaat, KNOWLEDGE_DIR


def fake_game(tmp: Path, edition: str = "enhanced", loader: str = "dinput8.dll") -> Path:
    g = tmp / "Game [x] (copy)"
    (g / "scripts" / "OtherMod").mkdir(parents=True)
    (g / "scripts" / "OtherMod" / "Main.cs").write_text("class X {}", encoding="utf-8")
    (g / "update/x64/dlcpacks").mkdir(parents=True)
    (g / "ScriptHookV.dll").write_bytes(b"MZ" + b"\0" * 100)
    (g / loader).write_bytes(b"MZ")
    (g / ("GTA5_Enhanced.exe" if edition == "enhanced" else "GTA5.exe")).write_bytes(b"MZ")
    (g / "args.txt").write_text("-nobattleye\n", encoding="utf-8")
    return g


def rsc7(sys_flags=0x90000001, gfx_flags=0x00000000, body=b"\x78\x9c" + b"\0" * 30) -> bytes:
    return struct.pack("<IIII", rpf7.RSC7_MAGIC, 0x9A, sys_flags, gfx_flags) + body


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gtaforge_test_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self._env = {k: os.environ.get(k) for k in ("GTA_FORGE_HOME", "GTA_FORGE_INDEX", "GTA_FORGE_ANIM_INDEX", "GTA5_ROOT")}
        os.environ["GTA_FORGE_HOME"] = str(self.tmp / "home")
        os.environ.pop("GTA_FORGE_INDEX", None)
        os.environ.pop("GTA_FORGE_ANIM_INDEX", None)
        self.addCleanup(self._restore)

    def _restore(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def cli(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main([str(a) for a in args])
        out = buf.getvalue()
        return code, (json.loads(out) if out.strip() else {})


class TestHashes(Base):
    def test_joaat_reference_values(self):
        self.assertEqual(joaat(""), "00000000")
        self.assertEqual(joaat("adder"), "b779a091")             # Adder model hash
        self.assertEqual(joaat("mp_m_freemode_01"), "705e61f2")  # Menyoo outfit file ModelHash
        self.assertEqual(joaat("ADDER"), joaat("adder"))           # case-insensitive

    def test_hash_command(self):
        f = self.tmp / "a.bin"
        f.write_bytes(b"hello")
        code, out = self.cli("hash", f)
        self.assertEqual((code, out["bytes"]), (0, 5))
        code, out = self.cli("hash", "--joaat", "adder", "zentorno")
        self.assertEqual(out["joaat"][0]["signed"], -1216765807)
        self.assertEqual(len(out["joaat"]), 2)


class TestNatives(Base):
    def test_db_complete_and_clean(self):
        from gtaforge.natives import _db
        db = _db()
        self.assertGreater(len(db), 6000)
        names = [n["name"] for n in db]
        self.assertEqual(len(names), len(set(names)))
        for n in db[:200]:
            self.assertRegex(n["hash"], r"^[0-9a-f]{1,16}$")
            self.assertIsInstance(n["params"], list)
            for p in n["params"]:
                self.assertIsInstance(p, dict)  # 0.2.0 stored params as JSON strings

    def test_lookup_by_name_hash_and_old_name(self):
        from gtaforge.natives import lookup, _db
        n = lookup("TASK_PLAY_ANIM")
        self.assertEqual(n["ns"], "TASK")
        self.assertEqual(len(n["params"]), 11)
        self.assertEqual(lookup("0x" + n["hash"].upper())["name"], "TASK_PLAY_ANIM")
        renamed = next(x for x in _db() if x.get("old_names"))
        self.assertEqual(lookup(renamed["old_names"][0])["name"], renamed["name"])
        code, out = self.cli("natives", "PLAYER_PED_ID")
        self.assertEqual(out["exact"]["ns"], "PLAYER")

    def test_header_generation(self):
        code, out = self.cli("natives", "--header", self.tmp / "natives.h")
        self.assertEqual(code, 0)
        text = (self.tmp / "natives.h").read_text(encoding="utf-8")
        self.assertIn("namespace TASK", text)
        self.assertIn("inline void TASK_PLAY_ANIM(Ped ped, const char* animDictionary", text)
        self.assertNotIn("invoke<Void>", text)


class TestRpf7(Base):
    def make_tree(self) -> Path:
        src = self.tmp / "src"
        (src / "data" / "sub").mkdir(parents=True)
        (src / "data" / "a.meta").write_text("<x>" + "y" * 5000 + "</x>", encoding="utf-8")
        (src / "data" / "sub" / "b.txt").write_bytes(os.urandom(700))  # incompressible: stored
        (src / "model.ydr").write_bytes(rsc7())
        inner = self.tmp / "inner"
        (inner / "x").mkdir(parents=True)
        (inner / "x" / "deep.xml").write_text("<deep/>", encoding="utf-8")
        rpf7.pack(inner, src / "nested.rpf")
        return src

    def test_pack_read_extract_roundtrip(self):
        src = self.make_tree()
        out = self.tmp / "dlc.rpf"
        r = rpf7.pack(src, out)
        self.assertEqual(out.read_bytes()[:4], b"7FPR")  # what real GTA V archives store
        head = rpf7.read_header(out)
        self.assertEqual((head["encryption"], head["readable_here"]), ("open", True))
        arc = rpf7.Archive.open(out)
        paths = {e.path for e in arc.files()}
        self.assertEqual(paths, {"data/a.meta", "data/sub/b.txt", "model.ydr", "nested.rpf"})
        self.assertEqual(arc.extract(arc.find("data/a.meta")), (src / "data" / "a.meta").read_bytes())
        self.assertEqual(arc.extract(arc.find("DATA\\SUB\\B.TXT")), (src / "data" / "sub" / "b.txt").read_bytes())
        res = arc.extract(arc.find("model.ydr"))
        self.assertEqual(res[:4], b"RSC7")
        self.assertEqual(struct.unpack_from("<I", res, 8)[0], 0x90000001)
        self.assertEqual(arc.find("model.ydr").kind, "rsc")
        nested = dict((p, e) for p, e, _a in arc.walk(nested=True))
        self.assertIn("nested.rpf/x/deep.xml", nested)
        self.assertEqual(r["files"], 4)

    def test_pack_is_deterministic(self):
        src = self.make_tree()
        a, b = self.tmp / "a.rpf", self.tmp / "b.rpf"
        rpf7.pack(src, a)
        rpf7.pack(src, b)
        self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_encrypted_header_reported_not_read(self):
        f = self.tmp / "enc.rpf"
        f.write_bytes(struct.pack("<IIII", rpf7.MAGIC, 705, 12240, 0x0FEFFFFF) + b"\0" * 64)
        self.assertEqual(rpf7.read_header(f)["encryption"], "ng")
        with self.assertRaises(ForgeError):
            rpf7.Archive.open(f)

    def test_damaged_and_foreign(self):
        f = self.tmp / "bad.rpf"
        f.write_bytes(struct.pack("<IIII", rpf7.MAGIC, 1000, 10, 0x4E45504F))
        with self.assertRaises(ForgeError):
            rpf7.Archive.open(f)
        g = self.tmp / "vi.rpf"
        g.write_bytes(b"9FPR" + b"\0" * 60)
        with self.assertRaisesRegex(ForgeError, "rpf9"):
            rpf7.read_header(g)

    def test_cli_list_find_extract_pack(self):
        src = self.make_tree()
        out = self.tmp / "dlc.rpf"
        code, r = self.cli("rpf", "pack", src, "--out", out)
        self.assertEqual(code, 0)
        code, r = self.cli("rpf", "list", out)
        self.assertEqual((code, r["engine"]), (0, "python"))
        code, r = self.cli("rpf", "find", out, "--pattern", "deep", "--nested")
        self.assertEqual(r["matched"], 1)
        code, r = self.cli("rpf", "extract", out, "--out", self.tmp / "x", "--nested")
        self.assertEqual(code, 0)
        self.assertTrue((self.tmp / "x" / "nested.rpf" / "x" / "deep.xml").is_file())
        code, r = self.cli("rpf", "info", out)
        self.assertEqual(r["format"], "rpf7")

    def test_extract_refuses_path_escape(self):
        evil = self.tmp / "evil"
        (evil / "zz").mkdir(parents=True)
        (evil / "zz" / "f.txt").write_text("x")
        out = self.tmp / "evil.rpf"
        rpf7.pack(evil, out)
        data = bytearray(out.read_bytes())
        i = data.index(b"\0zz\0") + 1
        data[i:i + 2] = b".."  # rename directory "zz" to ".." in the names table
        out.write_bytes(bytes(data))
        code, r = self.cli("rpf", "extract", out, "--out", self.tmp / "o")
        self.assertEqual(code, 2)
        self.assertFalse((self.tmp / "f.txt").exists())


class TestRpf9AndVi(Base):
    def rpf9_file(self, path: Path, nested: bool = True) -> Path:
        def header(length, split, files):
            h = bytearray(0x40)
            h[0:4] = b"9FPR"
            struct.pack_into("<IIIQ", h, 4, length, split, 0x20, 0x1122334455667788)
            struct.pack_into("<I", h, 0x24, files)
            return bytes(h)
        data = bytearray(0x3000)
        data[0:0x40] = header(0x40 + 16 * 6, 0x40 + 16 * 4, 4)
        if nested:
            data[0x1000:0x1040] = header(0x40 + 32, 0x40 + 16, 1)
        data[0x0800:0x0804] = b"9FPR"  # not on a sector boundary: must be ignored
        path.write_bytes(bytes(data))
        return path

    def test_rpf9_header_and_nested(self):
        r = rpf9.read(self.rpf9_file(self.tmp / "a.rpf"))
        self.assertEqual(r["header"]["records"], [4, 2])
        self.assertEqual(r["header"]["files"], 4)
        self.assertEqual(r["header"]["id"], "1122334455667788")
        self.assertEqual(r["nested"], 1)
        code, out = self.cli("rpf", "info", self.tmp / "a.rpf")
        self.assertEqual(out["format"], "rpf9")

    def test_sniff(self):
        for head, kind in ((b"7FPR", "rpf7"), (b"9FPR", "rpf9"), (b"8FPR", "rpf8"), (b"RSC7", "rsc7"), (b"ADAT", "awc"),
                           (b"RDS5", "ttpf-pool"), (b"MZ\x90\x00", "pe"), (b"zzzz", "unknown")):
            self.assertEqual(rpf9.sniff(head + b"\0" * 12), kind)

    def test_probe_census(self):
        d = self.tmp / "dump"
        (d / "x64").mkdir(parents=True)
        self.rpf9_file(d / "x64" / "a.rpf")
        (d / "GTA6.exe").write_bytes(b"MZ" + b"\0" * 100)
        (d / "v.rpf").write_bytes(struct.pack("<IIII", rpf7.MAGIC, 3, 16, 0x0FEFFFFF))
        (d / "song.awc").write_bytes(b"ADAT" + b"\0" * 12)
        (d / "misc.bin").write_bytes(b"\x01\x02\x03\x04" * 4)
        code, r = self.cli("vi", "probe", d, "--out", self.tmp / "probe.json")
        self.assertEqual(code, 0)
        self.assertEqual(r["archives"]["by_format"], {"rpf9": 1, "rpf7": 1})
        self.assertTrue(r["executables"][0]["looks_like_title"])
        self.assertIn("awc", r["census"])
        self.assertIn("RPF9", r["verdict"])
        self.assertTrue((self.tmp / "probe.json").is_file())

    def test_names_recovery(self):
        words = self.tmp / "words.txt"
        words.write_text("prop_casino_chair\nvw_prop_casino_slot_01a\nmini@strip_club@idles@stripper\n", encoding="utf-8")
        hashes = self.tmp / "hashes.txt"
        hashes.write_text("\n".join(["0x" + joaat("vw_prop_casino_slot_01a"), str(int(joaat("prop_casino_chair_hi"), 16)),
                                     "0xdeadbeef"]), encoding="utf-8")
        code, r = self.cli("vi", "names", hashes, "--words", words, "--no-index")
        self.assertEqual(code, 0)
        found = {m["name"] for m in r["matches"]}
        self.assertEqual(found, {"vw_prop_casino_slot_01a", "prop_casino_chair_hi"})  # second via a generated variant
        self.assertEqual(r["hashes"], 3)
        raw = self.tmp / "table.bin"
        raw.write_bytes(struct.pack("<3I", int(joaat("prop_casino_chair"), 16), 0x12345678, 0x9ABCDEF0))
        code, r = self.cli("vi", "names", raw, "--words", words, "--no-index")
        self.assertEqual(r["recovered"], 1)

    def test_checklist(self):
        code, r = self.cli("vi", "checklist")
        self.assertEqual(len(r["checks"]), 12)
        d = self.tmp / "d"
        d.mkdir()
        self.rpf9_file(d / "a.rpf")
        code, r = self.cli("vi", "checklist", d)
        self.assertEqual(r["checks"][1]["status"], "done")

    def test_status(self):
        code, out = self.cli("vi", "status")
        self.assertEqual(code, 0)
        self.assertIn("file_tools", out)


class TestScriptsCheck(Base):
    def test_cpp_natives_args_and_entry(self):
        d = self.tmp / "p"
        d.mkdir()
        (d / "CMakeLists.txt").write_text("project(x)")
        (d / "main.cpp").write_text(
            "#include \"natives.h\"\n"
            "BOOL APIENTRY DllMain(HMODULE h, DWORD r, LPVOID) { CreateThread(0,0,0,0,0,0); return TRUE; }\n"
            "void f() {\n"
            "  Ped p = PLAYER::PLAYER_PED_ID();\n"
            "  TASK::TASK_PLAY_ANIM(p, \"mini@strip_club@idles@stripper\", \"idle_a\", 8.0f, -8.0f, -1, 1, 0.0f, FALSE, FALSE, FALSE);\n"
            "  ENTITY::DOES_ENTITY_EXIST(p, 1);\n"
            "  PED::NOT_A_REAL_NATIVE_XYZ(p);\n"
            "  // PED::COMMENTED_OUT(p);\n"
            "}\n", encoding="utf-8")
        code, r = self.cli("script", "check", d)
        self.assertEqual(code, 1)
        probs = " | ".join(e["problem"] for e in r["errors"])
        self.assertIn("2 argument(s), native takes 1", probs)
        self.assertIn("not a GTA V native", probs)
        self.assertIn("scriptRegister", probs)
        self.assertNotIn("COMMENTED_OUT", json.dumps(r))
        self.assertEqual(r["native_calls"], 3)
        self.assertTrue(any("CreateThread" in w["problem"] for w in r["warnings"]))

    def test_cs_function_call(self):
        d = self.tmp / "c"
        d.mkdir()
        (d / "x.csproj").write_text("<Project/>")
        (d / "Main.cs").write_text(
            "Function.Call(Hash.SET_ENTITY_HEALTH, ped, 200, 0, 0);\n"
            "Function.Call<bool>(Hash.DOES_ENTITY_EXIST, ped);\n"
            "Function.Call(Hash.SET_ENTITY_HEALTH, ped);\n"
            "Function.Call((Hash)0x1111111111111111UL, ped);\n", encoding="utf-8")
        code, r = self.cli("script", "check", d)
        self.assertEqual(r["native_calls"], 3)
        self.assertEqual(len(r["errors"]), 2)


class TestProject(Base):
    def test_new_every_kind_and_check(self):
        for kind in ("cpp", "shvdn", "menyoo", "xml", "lua"):
            p = self.tmp / f"P_{kind}"
            code, out = self.cli("new", f"P_{kind}", "--folder", p, "--kind", kind, "--target-game", "enhanced")
            self.assertEqual(code, 0, out)
            m = json.loads((p / "gtaforge.json").read_text(encoding="utf-8"))
            self.assertEqual((m["schema"], m["kinds"]), (2, [kind]))
            code, out = self.cli("check", "--project", p)
            self.assertEqual(code, 0, out)
        self.assertTrue((self.tmp / "P_cpp" / "inc" / "natives.h").is_file())
        spooner = (self.tmp / "P_menyoo" / "menyooStuff" / "Spooner" / "P_menyoo.xml").read_text(encoding="utf-8")
        self.assertIn("0x" + joaat("prop_bench_01a"), spooner)

    def test_template_entry_point_is_scripthookv_correct(self):
        p = self.tmp / "A"
        self.cli("new", "A", "--folder", p, "--kind", "cpp")
        main_cpp = (p / "src" / "main.cpp").read_text(encoding="utf-8")
        self.assertIn("scriptRegister(module, ScriptMain)", main_cpp)
        self.assertNotIn("CreateThread", main_cpp)
        code, r = self.cli("script", "check", p)
        self.assertEqual(r["errors"], [])

    def test_bad_names_and_existing_folder(self):
        code, out = self.cli("new", "../evil", "--folder", self.tmp / "e")
        self.assertEqual(code, 2)
        p = self.tmp / "D"
        self.cli("new", "D", "--folder", p, "--kind", "xml")
        code, out = self.cli("new", "D", "--folder", p, "--kind", "cpp")
        self.assertEqual(code, 2)
        code, out = self.cli("new", "D", "--folder", p, "--kind", "cpp", "--force")
        self.assertEqual(code, 0)
        self.assertEqual(out["kinds"], ["xml", "cpp"])

    def test_bump_updates_changelog_and_csproj(self):
        p = self.tmp / "B"
        self.cli("new", "B", "--folder", p, "--kind", "shvdn")
        code, out = self.cli("bump", "minor", "--project", p)
        self.assertEqual(out["new"], "0.2.0")
        self.assertIn("## 0.2.0", (p / "CHANGELOG.md").read_text(encoding="utf-8"))
        self.assertIn("<Version>0.2.0</Version>", (p / "Plugin.csproj").read_text(encoding="utf-8"))

    def test_spooner_hash_mismatch_warns(self):
        p = self.tmp / "M"
        self.cli("new", "M", "--folder", p, "--kind", "menyoo")
        f = p / "menyooStuff" / "Spooner" / "M.xml"
        f.write_text(f.read_text(encoding="utf-8").replace("0x" + joaat("prop_bench_01a"), "0x12345678"), encoding="utf-8")
        code, out = self.cli("check", "--project", p)
        self.assertTrue(any("joaat" in w["problem"] for w in out["warnings"]))


class TestPayloadPackageDeploy(Base):
    def built_cpp(self) -> Path:
        p = self.tmp / "Mod"
        self.cli("new", "Mod", "--folder", p, "--kind", "cpp", "--kind", "menyoo")
        (p / "build").mkdir()
        (p / "build" / "Mod.asi").write_bytes(b"MZ-asi-v1")
        (p / "build" / "Mod.pdb").write_bytes(b"pdb")
        (p / "STATE.md").write_text("notes")
        return p

    def test_package_ships_payload_only_and_is_deterministic(self):
        p = self.built_cpp()
        code, a = self.cli("package", "--project", p, "--out", self.tmp / "a.zip")
        self.assertEqual(code, 0, a)
        self.assertEqual(a["names"], ["Mod.asi", "menyooStuff/Spooner/Mod.xml"])
        code, b = self.cli("package", "--project", p, "--out", self.tmp / "b.zip")
        self.assertEqual(a["sha256"], b["sha256"])
        code, v = self.cli("validate", self.tmp / "a.zip")
        self.assertEqual((code, v["problems"]), (0, []))

    def test_empty_payload_is_named(self):
        p = self.tmp / "E"
        self.cli("new", "E", "--folder", p, "--kind", "cpp")
        code, out = self.cli("package", "--project", p)
        self.assertEqual(code, 2)
        self.assertIn("compile", out["fix"])

    def test_validate_rejects_bad_zips(self):
        z = self.tmp / "bad.zip"
        with zipfile.ZipFile(z, "w") as f:
            f.writestr("src/main.cpp", "int x;")
            f.writestr("../escape.asi", "x")
            f.writestr("ScriptHookV.dll", "x")
            f.writestr("cfg.ini", "api_key = 'ABCDEFGHIJKLMNOPQRST'")
        code, v = self.cli("validate", z)
        self.assertEqual(code, 1)
        kinds = " | ".join(x["problem"] for x in v["problems"])
        for want in ("non-runtime", "escapes", "framework", "secret"):
            self.assertIn(want, kinds)
        (self.tmp / "nz.zip").write_text("not a zip")
        self.assertEqual(self.cli("validate", self.tmp / "nz.zip")[0], 2)

    def test_payload_escape_blocked(self):
        p = self.built_cpp()
        m = json.loads((p / "gtaforge.json").read_text(encoding="utf-8"))
        m["payload"] = [{"from": "build/*.asi", "to": "../../Windows"}]
        (p / "gtaforge.json").write_text(json.dumps(m), encoding="utf-8")
        self.assertEqual(self.cli("package", "--project", p)[0], 2)

    def test_deploy_keeps_first_original_and_restores_it(self):
        g = fake_game(self.tmp)
        (g / "Mod.asi").write_bytes(b"ORIGINAL")
        p = self.built_cpp()
        code, out = self.cli("deploy", "--project", p, "--game", g, "--dry-run")
        self.assertTrue(out["dry_run"])
        self.assertEqual((g / "Mod.asi").read_bytes(), b"ORIGINAL")
        code, out = self.cli("deploy", "--project", p, "--game", g)
        self.assertEqual((code, out["deployed"]), (0, 2))
        self.assertEqual((g / "Mod.asi").read_bytes(), b"MZ-asi-v1")
        self.assertFalse((g / "STATE.md").exists() or (g / "src").exists())
        (p / "build" / "Mod.asi").write_bytes(b"MZ-asi-v2")
        self.cli("deploy", "--project", p, "--game", g)  # second deploy must not back up v1 as "original"
        self.assertEqual((g / "Mod.asi").read_bytes(), b"MZ-asi-v2")
        code, out = self.cli("deploy", "--remove", "--project", p, "--game", g)
        self.assertEqual(code, 0)
        self.assertEqual((g / "Mod.asi").read_bytes(), b"ORIGINAL")
        self.assertFalse((g / "menyooStuff").exists())
        self.assertEqual(self.cli("deploy", "--remove", "--project", p, "--game", g)[0], 2)

    def test_deploy_lua_refused(self):
        g = fake_game(self.tmp)
        p = self.tmp / "L"
        self.cli("new", "L", "--folder", p, "--kind", "lua")
        self.assertEqual(self.cli("deploy", "--project", p, "--game", g)[0], 2)


class TestIndexBindings(Base):
    def fake_index(self) -> Path:
        d = self.tmp / "idx"
        d.mkdir()
        os.environ["GTA_FORGE_INDEX"] = str(d)
        rows = ["x64c.rpf/anim/ingame/clip_mini@.rpf/mini@strip_club@idles@stripper.ycd\tbin\t100",
                "update/x64/dlcpacks/mpvinewood/dlc.rpf/x64/anim/ingame/clip_anim_casino_b@.rpf/anim_casino_b@amb@casino@games@blackjack@dealer.ycd\tbin\t200",
                "x64e.rpf/levels/gta5/vehicles.rpf/adder.yft\trsc\t300",
                "x64f.rpf/levels/gta5/props/roadside/v_seating_tables.rpf/prop_bench_01a.ydr\trsc\t50"]
        with gzip.open(d / "enhanced-test.tsv.gz", "wt", encoding="utf-8") as f:
            f.write("\n".join(rows) + "\n")
        return d

    def test_find(self):
        self.fake_index()
        code, r = self.cli("find", "ADDER")
        self.assertTrue(r["found"])
        self.assertEqual(r["exact"][0]["kind"], "fragment")
        code, r = self.cli("find", "casino", "--ext", ".ycd")
        self.assertEqual((code, r["found"], r["partial_count"]), (0, False, 1))
        code, r = self.cli("find", "nothing_like_this")
        self.assertEqual(code, 1)

    def test_find_batch(self):
        self.fake_index()
        names = self.tmp / "n.txt"
        names.write_text("adder\n# comment\nADDER\nprop_bench_01a\nno_such_thing\n\n", encoding="utf-8")
        code, r = self.cli("find", "--batch", names)
        self.assertEqual((code, r["names"], r["found"], r["missing"]), (1, 3, 2, ["no_such_thing"]))
        self.assertEqual(self.cli("find")[0], 2)

    def test_no_index_is_named(self):
        os.environ["GTA_FORGE_INDEX"] = str(self.tmp / "none")
        self.assertEqual(self.cli("find", "adder")[0], 2)

    def test_bindings_coverage(self):
        self.fake_index()
        anim = self.tmp / "anim"
        anim.mkdir()
        (anim / "a.json").write_text(json.dumps({"mini@strip_club@idles@stripper": ["idle_a", "idle_b"]}), encoding="utf-8")
        os.environ["GTA_FORGE_ANIM_INDEX"] = str(anim)
        keys = self.tmp / "keys.json"
        keys.write_text(json.dumps({"keys": {
            "adult.strip.idle": {"module": "adult", "type": "anim", "required": True},
            "adult.strip.bad_clip": {"module": "adult", "type": "anim"},
            "casino.blackjack.dealer": {"module": "casino", "type": "anim", "required": True},
            "casino.table": {"module": "casino", "type": "prop", "required": True},
            "life.car": {"module": "life", "type": "vehicle"},
            "life.ghost": {"module": "life", "type": "model", "required": True},
        }}), encoding="utf-8")
        table = self.tmp / "gta5.json"
        table.write_text(json.dumps({"game": "gta5", "bindings": {
            "adult.strip.idle": {"dict": "mini@strip_club@idles@stripper", "clip": "idle_a"},
            "adult.strip.bad_clip": {"dict": "mini@strip_club@idles@stripper", "clip": "nope"},
            "casino.blackjack.dealer": {"dict": "anim_casino_b@amb@casino@games@blackjack@dealer"},
            "casino.table": {"model": "vw_prop_casino_blckjack_01"},
            "life.car": "adder",
            "life.ghost": None,
            "stray.key": "x"}}), encoding="utf-8")
        code, r = self.cli("bindings", keys, table)
        self.assertEqual(code, 1)
        st = {row["key"]: row["status"] for row in r["rows"]}
        self.assertEqual(st["adult.strip.idle"], "verified")
        self.assertEqual(st["adult.strip.bad_clip"], "clip not in anim index")
        self.assertEqual(st["casino.blackjack.dealer"], "verified")
        self.assertEqual(st["casino.table"], "asset not in game")
        self.assertEqual(st["life.car"], "verified")
        self.assertEqual(st["life.ghost"], "declared-missing")
        self.assertEqual(r["unknown_keys_in_table"], ["stray.key"])
        self.assertEqual(r["modules"]["casino"]["coverage"], 1.0)


class TestGameDoctor(Base):
    def test_detects_awkward_path_and_any_loader(self):
        g = fake_game(self.tmp, loader="xinput1_4.dll")
        code, out = self.cli("game", "--game", g)
        self.assertEqual(code, 0)
        fw = {f["id"]: f for f in out["frameworks"]}
        self.assertTrue(fw["asi_loader"]["installed"])  # 0.2.0 required all three loader names at once
        self.assertEqual(out["version"]["edition"], "enhanced")

    def test_file_version_python_reader(self):
        from gtaforge.util import file_version
        exe = self.tmp / "GTA5_Enhanced.exe"
        fixed = struct.pack("<IIII", 0xFEEF04BD, 0x00010000, (1 << 16) | 0, (1158 << 16) | 16)
        exe.write_bytes(b"MZ" + b"\0" * 500 + fixed + b"\0" * 64)
        self.assertEqual(file_version(exe), "1.0.1158.16")
        (self.tmp / "plain.exe").write_bytes(b"MZ" + b"\0" * 100)
        self.assertIsNone(file_version(self.tmp / "plain.exe"))
        self.assertIsNone(file_version(self.tmp / "missing.exe"))

    def test_rejects_non_game(self):
        self.assertEqual(self.cli("game", "--game", self.tmp)[0], 2)

    def test_doctor_sections(self):
        code, out = self.cli("doctor", "--game", self.tmp / "nope")
        self.assertEqual((code, out["game"]["status"]), (2, "missing"))
        g = fake_game(self.tmp)
        code, out = self.cli("doctor", "--game", g)
        for section in ("cli", "payload", "game", "build", "archives", "index", "vi", "tools"):
            self.assertIn(section, out)
        self.assertEqual(out["payload"]["status"], "ok", out["payload"])
        self.assertEqual(out["game"]["missing_core"], [])

    def test_logs_and_conflicts(self):
        g = fake_game(self.tmp)
        (g / "ScriptHookV.log").write_text("ok\nERROR something failed\n", encoding="utf-8")
        code, out = self.cli("logs", "--game", g)
        self.assertEqual(out["logs"][0]["errors"], 1)
        code, out = self.cli("conflicts", "--project", self.tmp / "P", "--game", g)
        self.assertEqual(code, 2)


class TestMenyooAnims(Base):
    def test_index_and_lookup(self):
        m = self.tmp / "menyooStuff"
        m.mkdir()
        (m / "PedAnimList.txt").write_text("mini@strip_club@idles@stripper idle_a\nmini@prostitutes@sexnorm_veh bj_loop_male\n", encoding="utf-8")
        for f in ("PedSpeechList.txt", "PropList.txt", "PedList.xml", "CutsceneLabels.txt"):
            (m / f).write_text("x", encoding="utf-8")
        out = self.tmp / "idx"
        code, r = self.cli("menyoo", "index", "--folder", m, "--out", out)
        self.assertEqual((code, r["dicts"]), (0, 2))
        os.environ["GTA_FORGE_ANIM_INDEX"] = str(out)
        code, r = self.cli("anim", "--dict", "mini@strip_club@idles@stripper")
        self.assertTrue(r["found"])
        code, r = self.cli("anim", "--pattern", "prostitutes")
        self.assertEqual(r["dicts"], 1)


class TestClipParsing(Base):
    def test_parse_ragekit_info(self):
        from gtaforge.anims import parse_info
        text = ("clip dictionary: 3 clips, 2 animations, 9 structures\n  clips: 3\n"
                "    pack:/stripper_idle_01.clip: animation, 0.000 .. 3.0 s\n"
                "    pack:/female_turn_card_facial.clip: animation, 1 .. 2 s\n"
                "    plain_name.clip: list, 0 .. 1 s\n  animations: 2\n    hash_F27BA174: 10 frames\n")
        self.assertEqual(parse_info(text), ["female_turn_card_facial", "plain_name", "stripper_idle_01"])

    def test_clips_needs_dict_and_named_errors(self):
        self.assertEqual(self.cli("anim", "clips")[0], 2)
        self.assertEqual(self.cli("anim", "build")[0], 2)


class TestKnowledgeAndCli(Base):
    def test_routes_name_existing_docs(self):
        routes = json.loads((KNOWLEDGE_DIR / "routes.json").read_text(encoding="utf-8"))
        for r in routes["routes"]:
            for d in r["docs"]:
                self.assertTrue((KNOWLEDGE_DIR / d).is_file(), f"route {r['id']} -> missing {d}")

    def test_plan_routes(self):
        from gtaforge.knowledge import plan
        self.assertEqual(plan("add a blackjack table to the casino")["route"]["id"], "casino")
        self.assertEqual(plan("read the gta 6 rpf9 archives")["route"]["id"], "vi")

    def test_no_command_crashes_on_bad_input(self):
        """Every subcommand, given nothing or garbage, answers with JSON and exit 0/1/2 - never 3."""
        p = parser()
        names = [n for a in p._subparsers._group_actions for n in a.choices]
        cwd = os.getcwd()
        os.chdir(self.tmp)  # `new <garbage>` legitimately creates a folder: keep it in the temp dir
        self.addCleanup(os.chdir, cwd)
        bad_inputs = [[], ["--nonsense"], ["zz-not-a-thing"], [str(self.tmp / "missing" / "x.rpf")]]
        for name in names:
            if name in ("index",):  # index build would scan a real game when one is installed
                continue
            for extra in bad_inputs:
                code, out = self.cli(name, *extra, "--game", self.tmp / "no_game", "--project", self.tmp / "no_project")
                self.assertIn(code, (0, 1, 2), f"{name} {extra}: {out}")
                if code == 2:
                    self.assertTrue(out.get("fix"), f"{name} {extra}: exit 2 without a fix: {out}")

    def test_capabilities_cover_parser(self):
        code, out = self.cli("capabilities")
        cmds = {c["command"] for c in out["commands"]}
        for want in ("rpf", "index", "find", "vi", "bindings", "natives", "deploy", "compile"):
            self.assertIn(want, cmds)


@unittest.skipUnless(os.name == "nt", "Windows launcher")
class TestLauncher(Base):
    def test_cmd_launcher_propagates_exit_codes(self):
        """0.2.0's launcher expanded %ERRORLEVEL% inside an if-block: every exit code came back 0."""
        import subprocess
        cmd = str(ROOT / "gtaforge.cmd")
        ok = subprocess.run(["cmd", "/c", cmd, "hash", "--joaat", "adder"], capture_output=True, text=True)
        bad = subprocess.run(["cmd", "/c", cmd, "hash", "--joaat"], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertEqual(bad.returncode, 2, bad.stdout + bad.stderr)


class TestVersionMirrors(Base):
    def test_mirrors(self):
        for f in ("CHANGELOG.md", "STATE.md", "skills/gta-forge/SKILL.md", "README.md"):
            self.assertIn(__version__, (ROOT / f).read_text(encoding="utf-8"), f)


if __name__ == "__main__":
    unittest.main()
