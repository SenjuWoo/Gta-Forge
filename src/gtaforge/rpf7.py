"""RPF7 (GTA V Legacy + Enhanced) in pure Python.

Layout (verified against ragekit src/rpf.cpp + src/rpf_write.cpp and the installed
Enhanced archives, whose first four bytes read b"7FPR" = uint32 0x52504637 little endian):

  header 16 bytes : magic u32, entry_count u32, names_length u32, encryption u32
  entry table     : entry_count x 16 bytes (encrypted when encryption is AES/NG)
  names table     : names_length bytes, NUL separated, padded to 16
  data            : 512-byte blocks, offsets in blocks from the archive start

Entry (16 bytes), told apart by the u32 at +4:
  directory : u32 name_off, u32 0x7FFFFF00, u32 first_child, u32 child_count
  binary    : 8 bytes {name_off:16, stored:24, block:24}, u32 uncompressed, u32 encrypted(0/1)
              stored == 0 means kept uncompressed; otherwise raw deflate of `stored` bytes
  resource  : bit 31 of byte 7 set; name_off:16, stored:24, block:23, u32 sys_flags, u32 gfx_flags
              on disk: a 16-byte header then a raw-deflate stream; extracting rebuilds the RSC7
              header (magic, version, sys, gfx) from the entry. stored == 0xFFFFFF means the real
              size is scrambled into bytes 7,14,5,2 of the on-disk header.

Encrypted (AES / NG) tables need the game's keys; this module reads only NONE/OPEN archives
and reports the encryption kind for the rest (the ragekit route in rpf.py handles those).
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from .util import ForgeError

MAGIC = 0x52504637          # bytes b"7FPR" on disk
RSC7_MAGIC = 0x37435352     # bytes b"RSC7" on disk
BLOCK = 512
DIR_MARK = 0x7FFFFF00
ENCRYPTION = {0: "none", 0x4E45504F: "open", 0x0FFFFFF9: "aes", 0x0FEFFFFF: "ng"}
PLAIN = ("none", "open")
# Page-class bit fields of a resource flags word (ragekit rsc.cpp kFields): (pos, bits)
_PAGE_FIELDS = ((4, 1), (5, 2), (7, 4), (11, 6), (17, 7), (24, 1), (25, 1), (26, 1), (27, 1))


def page_total(flags: int) -> int:
    """Bytes a resource segment occupies once loaded (sum of page class counts x page sizes)."""
    base = 0x200 << (flags & 0xF)
    return sum(((flags >> pos) & ((1 << bits) - 1)) * (base << (8 - i)) for i, (pos, bits) in enumerate(_PAGE_FIELDS))


def encryption_name(value: int) -> str:
    return ENCRYPTION.get(value, f"unknown(0x{value:08X})")


@dataclass
class Entry:
    index: int
    kind: str                     # dir | bin | rsc
    name: str = ""
    path: str = ""
    first_child: int = 0
    child_count: int = 0
    block: int = 0
    stored: int = 0
    uncompressed: int = 0
    encrypted: bool = False
    sys_flags: int = 0
    gfx_flags: int = 0

    @property
    def size(self) -> int:
        if self.kind == "bin":
            return self.uncompressed
        if self.kind == "rsc":
            return page_total(self.sys_flags) + page_total(self.gfx_flags)
        return 0

    @property
    def resource_version(self) -> int:
        return ((self.sys_flags >> 28) << 4) + (self.gfx_flags >> 28)

    def as_dict(self) -> dict:
        d = {"path": self.path, "kind": self.kind}
        if self.kind == "dir":
            d["children"] = self.child_count
        else:
            d.update(size=self.size, stored=self.stored)
            if self.kind == "rsc":
                d["version"] = self.resource_version
            if self.encrypted:
                d["encrypted"] = True
        return d


def read_header(path: Path) -> dict:
    """Header of any RPF7 file (encrypted or not). Raises ForgeError for other formats."""
    with open(path, "rb") as f:
        head = f.read(16)
    if len(head) < 16:
        raise ForgeError(f"too small to be an archive: {path}", "pass a .rpf file")
    magic, count, names_len, enc = struct.unpack("<IIII", head)
    if magic != MAGIC:
        from .rpf9 import sniff
        kind = sniff(head)
        raise ForgeError(f"not an RPF7 archive ({kind}): {path}",
                         "GTA VI archives are RPF9: gtaforge vi probe <folder>" if kind == "rpf9" else "pass a GTA V .rpf")
    return {"format": "rpf7", "entries": count, "names_length": names_len, "encryption": encryption_name(enc),
            "readable_here": encryption_name(enc) in PLAIN, "bytes": path.stat().st_size}


class Archive:
    """An unencrypted RPF7 held in memory (or a slice of a parent for nested archives)."""

    def __init__(self, data: bytes, name: str = "archive.rpf"):
        self.data = data
        self.name = name
        if len(data) < 16:
            raise ForgeError(f"{name}: too small to be an RPF", "pass a .rpf file")
        magic, count, names_len, enc = struct.unpack_from("<IIII", data, 0)
        if magic != MAGIC:
            raise ForgeError(f"{name}: not an RPF7 archive", "pass a GTA V .rpf")
        self.encryption = encryption_name(enc)
        if self.encryption not in PLAIN:
            raise ForgeError(f"{name}: table is {self.encryption.upper()} encrypted",
                             "use the ragekit route: gtaforge rpf keys, then gtaforge rpf list (needs ragekit + the game exe)")
        if 16 + count * 16 + names_len > len(data):
            raise ForgeError(f"{name}: table larger than the archive", "file is truncated or not an RPF")
        names = data[16 + count * 16: 16 + count * 16 + names_len]
        self.entries: list[Entry] = []
        for i in range(count):
            off = 16 + i * 16
            y, x, a, b = struct.unpack_from("<IIII", data, off)
            if x == DIR_MARK:
                e = Entry(i, "dir", first_child=a, child_count=b)
                name_off = y
            elif x & 0x80000000 == 0:
                buf = struct.unpack_from("<Q", data, off)[0]
                name_off = buf & 0xFFFF
                if b > 1:
                    raise ForgeError(f"{name}: bad file entry {i}", "archive is damaged")
                e = Entry(i, "bin", stored=(buf >> 16) & 0xFFFFFF, block=(buf >> 40) & 0xFFFFFF, uncompressed=a, encrypted=b == 1)
            else:
                p = data[off:off + 8]
                name_off = p[0] | p[1] << 8
                stored = p[2] | p[3] << 8 | p[4] << 16
                block = (p[5] | p[6] << 8 | p[7] << 16) & 0x7FFFFF
                if stored == 0xFFFFFF:
                    h = data[block * BLOCK: block * BLOCK + 16]
                    stored = h[7] | h[14] << 8 | h[5] << 16 | h[2] << 24
                e = Entry(i, "rsc", stored=stored, block=block, sys_flags=a, gfx_flags=b)
            if name_off < len(names):
                end = names.find(b"\0", name_off)
                e.name = names[name_off: end if end >= 0 else len(names)][:256].decode("utf-8", "replace")
            if e.kind == "rsc":
                e.encrypted = e.name.lower().endswith(".ysc")
            self.entries.append(e)
        if not self.entries or self.entries[0].kind != "dir":
            raise ForgeError(f"{name}: no root directory", "archive is damaged")
        seen = {0}
        stack = [0]
        while stack:
            d = self.entries[stack.pop()]
            if d.first_child + d.child_count > count:
                raise ForgeError(f"{name}: directory '{d.name}' lists entries past the table", "archive is damaged")
            for c in range(d.first_child, d.first_child + d.child_count):
                if c in seen:
                    continue
                seen.add(c)
                ch = self.entries[c]
                ch.path = f"{d.path}/{ch.name}" if d.path else ch.name
                if ch.kind == "dir":
                    stack.append(c)
        self._by_path = {e.path.lower(): e for e in self.entries}

    @classmethod
    def open(cls, path: Path) -> "Archive":
        return cls(Path(path).read_bytes(), Path(path).name)

    def files(self) -> list[Entry]:
        return [e for e in self.entries if e.kind != "dir"]

    def find(self, path: str) -> Entry | None:
        return self._by_path.get(path.replace("\\", "/").strip("/").lower())

    def _stored_bytes(self, e: Entry) -> bytes:
        n = (e.stored or e.uncompressed) if e.kind == "bin" else e.stored
        start = e.block * BLOCK
        if start + n > len(self.data):
            raise ForgeError(f"{self.name}: '{e.path}' lies outside the archive", "archive is truncated")
        return self.data[start:start + n]

    def extract(self, e: Entry) -> bytes:
        if e.kind == "dir":
            raise ForgeError(f"'{e.path}' is a directory", "pass a file path")
        if e.encrypted:
            raise ForgeError(f"'{e.path}' is encrypted inside a plain archive", "use the ragekit route (gtaforge rpf keys)")
        raw = self._stored_bytes(e)
        if e.kind == "bin":
            return inflate(raw, e.uncompressed) if e.stored else raw
        if len(raw) < 16:
            raise ForgeError(f"'{e.path}': resource smaller than its header", "archive is damaged")
        return struct.pack("<IIII", RSC7_MAGIC, e.resource_version, e.sys_flags, e.gfx_flags) + raw[16:]

    def child(self, e: Entry) -> "Archive":
        if e.kind != "bin" or not e.name.lower().endswith(".rpf"):
            raise ForgeError(f"'{e.path}' is not a nested archive", "pass a .rpf entry")
        return Archive(self._stored_bytes(e) if not e.stored else self.extract(e), e.name)

    def walk(self, nested: bool = False, prefix: str = ""):
        """Yield (full path, Entry, Archive) for every entry; nested archives descend when asked."""
        for e in self.entries[1:]:
            full = f"{prefix}{e.path}"
            yield full, e, self
            if nested and e.kind == "bin" and e.name.lower().endswith(".rpf"):
                try:
                    sub = self.child(e)
                except ForgeError:
                    continue
                yield from sub.walk(True, full + "/")


def inflate(raw: bytes, hint: int = 0) -> bytes:
    """Raw deflate (what RPF7 stores); falls back to a zlib-wrapped stream."""
    for wbits in (-15, 15):
        try:
            d = zlib.decompressobj(wbits)
            out = d.decompress(raw) + d.flush()
            if not hint or len(out) == hint:
                return out
        except zlib.error:
            continue
    raise ForgeError("deflate stream is damaged", "re-export the file")


def _deflate(data: bytes) -> bytes:
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return c.compress(data) + c.flush()


@dataclass
class _Node:
    name: str
    kind: str = "dir"             # dir | file
    data: bytes = b""
    kids: dict = field(default_factory=dict)


def _is_resource(data: bytes) -> bool:
    return len(data) >= 16 and struct.unpack_from("<I", data, 0)[0] == RSC7_MAGIC


def pack(src: Path, out: Path, encryption: str = "open", compress: bool = True) -> dict:
    """Write a folder as an unencrypted RPF7 (OPEN by default, as OpenIV/CodeWalker write for mods).

    Order follows ragekit: a directory's children are contiguous and sorted by name, directories
    expanded depth-first preorder. RSC7 files become resource entries; .rpf files are stored
    uncompressed so the game can open them in place; other files are raw-deflated when smaller.
    """
    src, out = Path(src), Path(out)
    if not src.is_dir():
        raise ForgeError(f"no folder: {src}", "pass the folder that becomes the archive root")
    if encryption not in PLAIN:
        raise ForgeError(f"Python packs plain archives only (none|open), not {encryption}", "use ragekit: ragekit rpf pack <dir> <out> --ng")
    root = _Node("")
    for p in sorted(src.rglob("*")):
        if p.is_dir() or p.resolve() == out.resolve():
            continue
        parts = p.relative_to(src).parts
        node = root
        for part in parts[:-1]:
            node = node.kids.setdefault(part.lower(), _Node(part.lower()))
        node.kids[parts[-1].lower()] = _Node(parts[-1].lower(), "file", p.read_bytes())
    flat: list[list] = [[root, 0, 0]]          # node, first, count
    stack = [0]
    while stack:
        di = stack.pop()
        kids = sorted(flat[di][0].kids.values(), key=lambda n: n.name)
        flat[di][1], flat[di][2] = len(flat), len(kids)
        base = len(flat)
        flat.extend([k, 0, 0] for k in kids)
        for i in reversed(range(len(kids))):
            if kids[i].kind == "dir":
                stack.append(base + i)
    names = bytearray()
    offsets: dict[str, int] = {}
    name_off = []
    for node, _f, _c in flat:
        if node.name not in offsets:
            offsets[node.name] = len(names)
            names += node.name.encode("utf-8") + b"\0"
        name_off.append(offsets[node.name])
    while len(names) % 16:
        names.append(0)
    if max(name_off, default=0) > 0xFFFF:
        raise ForgeError("names table too large (over 64 KiB)", "split the folder into nested archives")
    header_blocks = (16 + len(flat) * 16 + len(names) + BLOCK - 1) // BLOCK
    table = bytearray(len(flat) * 16)
    body = bytearray()
    block = header_blocks
    for i, (node, first, count) in enumerate(flat):
        off = i * 16
        if node.kind == "dir":
            struct.pack_into("<IIII", table, off, name_off[i], DIR_MARK, first, count)
            continue
        data = node.data
        if _is_resource(data):
            _m, _v, sysf, gfxf = struct.unpack_from("<IIII", data, 0)
            size_field = len(data)
            if size_field >= 0xFFFFFF:
                d = bytearray(data)
                n = len(d)
                d[7], d[14], d[5], d[2] = n & 0xFF, (n >> 8) & 0xFF, (n >> 16) & 0xFF, (n >> 24) & 0xFF
                data, size_field = bytes(d), 0xFFFFFF
            if block > 0x7FFFFF:
                raise ForgeError("archive too large for resource offsets", "split it")
            table[off:off + 8] = bytes((name_off[i] & 0xFF, name_off[i] >> 8, size_field & 0xFF, (size_field >> 8) & 0xFF,
                                        (size_field >> 16) & 0xFF, block & 0xFF, (block >> 8) & 0xFF, ((block >> 16) & 0x7F) | 0x80))
            struct.pack_into("<II", table, off + 8, sysf, gfxf)
            payload = data
        else:
            stored = 0
            payload = data
            if compress and not node.name.endswith(".rpf") and data:
                z = _deflate(data)
                if len(z) < len(data):
                    payload, stored = z, len(z)
            if stored > 0xFFFFFF or (not stored and len(data) > 0xFFFFFFFF):
                raise ForgeError(f"'{node.name}' too large for an RPF7 entry", "split it")
            if block > 0xFFFFFF:
                raise ForgeError("archive too large for file offsets", "split it")
            packed = name_off[i] | (stored << 16) | (block << 40)
            struct.pack_into("<QII", table, off, packed, len(data), 0)
        body += payload + b"\0" * ((-len(payload)) % BLOCK)
        block += (len(payload) + BLOCK - 1) // BLOCK
    enc_value = 0x4E45504F if encryption == "open" else 0
    head = struct.pack("<IIII", MAGIC, len(flat), len(names), enc_value) + bytes(table) + bytes(names)
    head += b"\0" * (header_blocks * BLOCK - len(head))
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".gtaforge_tmp")
    tmp.write_bytes(head + bytes(body))
    tmp.replace(out)
    return {"archive": str(out), "entries": len(flat), "files": sum(1 for n, _a, _b in flat if n.kind == "file"),
            "encryption": encryption, "bytes": out.stat().st_size}
