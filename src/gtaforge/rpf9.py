"""GTA VI RPF9 headers and file-signature sniffing. No keys needed; nothing is decrypted.

RPF9 header (64 bytes), from 6to5m src/container.rs (read 2026-11-24 against the console dump):
  0x00 magic b"9FPR"          0x04 u32 len   (header + both tables; tables are 16-byte records)
  0x08 u32 split (header + first table)    0x0C u32 trailer length
  0x10 u64 id                 0x20 u16[2] unknown   0x24 u32 files   0x28 u32 unknown   0x2C u16[2] unknown
Records: (split - 64) / 16 in table 1, (len - split) / 16 in table 2. Tables are encrypted.
Nested archives start on 0x1000 sector boundaries inside the outer archive.
"""
from __future__ import annotations

import mmap
import struct
from pathlib import Path

from .util import ForgeError

HEADER = 0x40
RECORD = 16
SECTOR = 0x1000

# First bytes -> (kind, description). Order matters only for shared prefixes.
SIGNATURES = (
    (b"7FPR", "rpf7", "RPF7 archive (GTA V)"),
    (b"8FPR", "rpf8", "RPF8 archive (RDR2)"),
    (b"9FPR", "rpf9", "RPF9 archive (GTA VI)"),
    (b"RPF6", "rpf6", "RPF6 archive (RDR / Max Payne 3)"),
    (b"RPF7", "rpf7-be", "RPF7 big-endian (console)"),
    (b"RSC7", "rsc7", "RSC7 resource (GTA V)"),
    (b"RSC8", "rsc8", "RSC8 resource (RDR2)"),
    (b"RSC9", "rsc9", "RSC9 resource"),
    (b"RDS5", "ttpf-pool", "TTPF texture pool (GTA VI)"),
    (b"ETPF", "etpf", "ETPF texture header (GTA VI)"),
    (b"ADAT", "awc", "AWC audio bank"),
    (b"TADA", "awc-be", "AWC audio bank (big-endian)"),
    (b"PSIN", "pso", "PSO metadata"),
    (b"RBF0", "rbf", "RBF metadata"),
    (b"MZ", "pe", "Windows executable / DLL"),
    (b"DDS ", "dds", "DDS texture"),
    (b"\x89PNG", "png", "PNG image"),
    (b"OggS", "ogg", "Ogg stream"),
    (b"RIFF", "riff", "RIFF (WAV/AVI/WEBP)"),
    (b"<?xml", "xml", "XML"),
    (b"\xef\xbb\xbf<?xml", "xml", "XML"),
    (b"PK\x03\x04", "zip", "ZIP"),
)


def sniff(head: bytes) -> str:
    for sig, kind, _desc in SIGNATURES:
        if head.startswith(sig):
            return kind
    if head[:4] in (b"\x7fELF",):
        return "elf"
    return "unknown"


def describe(kind: str) -> str:
    return next((d for _s, k, d in SIGNATURES if k == kind), kind)


def parse_header(buf: bytes, at: int = 0, size: int | None = None) -> dict | None:
    """One RPF9 header at `at`, or None. `size` bounds the archive (defaults to len(buf))."""
    h = buf[at:at + HEADER]
    if len(h) < HEADER or h[:4] != b"9FPR":
        return None
    length, split, trailer = struct.unpack_from("<III", h, 4)
    if split < HEADER or length < split or (split - HEADER) % RECORD or (length - split) % RECORD:
        return None
    limit = size if size is not None else len(buf)
    if at + length > limit:
        return None
    ident = struct.unpack_from("<Q", h, 0x10)[0]
    u1 = struct.unpack_from("<HH", h, 0x20)
    files = struct.unpack_from("<I", h, 0x24)[0]
    u2 = struct.unpack_from("<I", h, 0x28)[0]
    u3 = struct.unpack_from("<HH", h, 0x2C)
    return {"at": at, "len": length, "split": split, "trailer": trailer, "id": f"{ident:016x}", "files": files,
            "records": [(split - HEADER) // RECORD, (length - split) // RECORD], "unknown": [list(u1), u2, list(u3)]}


def read(path: Path, nested: bool = True, max_nested: int = 100_000) -> dict:
    """Outer header plus every nested RPF9 header on a sector boundary (memory-mapped; read-only)."""
    path = Path(path)
    size = path.stat().st_size
    if size < HEADER:
        raise ForgeError(f"too small for RPF9: {path}", "pass a GTA VI .rpf")
    with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
        outer = parse_header(m, 0, size)
        if outer is None:
            raise ForgeError(f"not an RPF9 archive ({sniff(m[:8])}): {path}", "gtaforge vi probe <folder> lists what it is")
        found = []
        if nested:
            at = SECTOR
            while at + HEADER <= size and len(found) < max_nested:
                at = m.find(b"9FPR", at)
                if at < 0:
                    break
                if at % SECTOR == 0:
                    h = parse_header(m, at, size)
                    if h:
                        found.append(h)
                at = (at // SECTOR + 1) * SECTOR
    return {"format": "rpf9", "path": str(path), "bytes": size, "header": outer, "nested": len(found),
            "nested_headers": found[:50], "tables": "encrypted (6to5m / 6ixpack decodes them)"}
