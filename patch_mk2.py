"""MK2 patch for Maschine 3: reuses the Maschine Jam subscription block (PID 0x1500)
so it sends PID_CONNECT for the Maschine MK2 (PID 0x1140), using the free slot +0x368.

Usage:
    python patch_mk2.py <input.exe> <output.exe>            apply the patch
    python patch_mk2.py <input.exe> <output.exe> --revert   undo it

Binaries analyzed (SHA-256 in VERSIONS) are patched at their known offsets. Any other Maschine 3.x
build is patched only if its Jam block is found exactly once with the expected layout; anything else aborts.
Never modifies the input file.
"""
import hashlib
import os
import re
import sys

# SHA-256 of the original .exe -> (version, [(file offset, VA, original bytes, patched bytes, description)])
VERSIONS = {
    "968c0d3fc5e8e1f145b5ad95ab9862ac8cec508ccfea4768f09a85e5c9b2393a": ("3.6.0", [
        (0x5DD32D, 0x1405DDF2D, bytes.fromhex("480508030000"), bytes.fromhex("480568030000"),
         "ADD RAX,0x308 (Jam subscription) -> ADD RAX,0x368 (MK2 subscription)"),
        (0x5DD37D, 0x1405DDF7D, bytes.fromhex("BA00150000"), bytes.fromhex("BA40110000"),
         "MOV EDX,0x1500 (Jam PID) -> MOV EDX,0x1140 (MK2 PID)"),
    ]),
    "432948f7da644f092312c1c35dbc93c74185b4a7cd1fc869e444bcc6f8b7f20b": ("3.7.1", [
        (0x5C08ED, 0x1405C14ED, bytes.fromhex("480508030000"), bytes.fromhex("480568030000"),
         "ADD RAX,0x308 (Jam subscription) -> ADD RAX,0x368 (MK2 subscription)"),
        (0x5C093D, 0x1405C153D, bytes.fromhex("BA00150000"), bytes.fromhex("BA40110000"),
         "MOV EDX,0x1500 (Jam PID) -> MOV EDX,0x1140 (MK2 PID)"),
    ]),
}

# Layout shared by every analyzed version: MOV EDX,<PID> followed by MOV R9D,'prmy' / MOV R8D,'NiM3',
# with the ADD RAX,<slot> 0x50 bytes before the MOV.
ADD_ORIG, ADD_NEW = bytes.fromhex("480508030000"), bytes.fromhex("480568030000")
MOV_ORIG, MOV_NEW = bytes.fromhex("BA00150000"), bytes.fromhex("BA40110000")
JAM_TAIL = bytes.fromhex("41B9796D727041B8334D694E")
ADD_DISTANCE = 0x50


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def apply(data, patches, revert):
    """Applies (or reverts) the patches on a copy; returns None if any byte does not match."""
    out = bytearray(data)
    log = []
    for off, va, orig, new, desc in patches:
        expect, write = (new, orig) if revert else (orig, new)
        found = bytes(out[off:off + len(expect)])
        if found != expect:
            return None, f"at {va:#x} (offset {off:#x}): expected {expect.hex(' ')}, found {found.hex(' ')}"
        out[off:off + len(write)] = write
        log.append(f"{'reverted' if revert else 'patched'} {va:#x} @ {off:#x}: {found.hex(' ')} -> {write.hex(' ')}  ({desc})")
    return out, log


def file_to_va(data, off):
    """Maps a file offset to its virtual address using the PE section table; None if it is not in a section."""
    u16, u32 = (lambda p: int.from_bytes(data[p:p + 2], "little")), (lambda p: int.from_bytes(data[p:p + 4], "little"))
    if data[:2] != b"MZ":
        return None
    pe = u32(0x3C)
    if data[pe:pe + 4] != b"PE\0\0":
        return None
    opt = pe + 24
    image_base = int.from_bytes(data[opt + 24:opt + 32], "little") if u16(opt) == 0x20B else u32(opt + 28)
    sections = opt + u16(pe + 20)
    for i in range(u16(pe + 6)):
        s = sections + 40 * i
        vaddr, raw_size, raw_ptr = u32(s + 12), u32(s + 16), u32(s + 20)
        if raw_ptr <= off < raw_ptr + raw_size:
            return image_base + vaddr + off - raw_ptr
    return None


def file_version(data):
    """Reads FileVersion from the version resource (e.g. "3.7.1"), or None."""
    key = "FileVersion".encode("utf-16-le") + b"\0\0"
    for m in reversed(list(re.finditer(re.escape(key), data))):
        p = m.end()
        while p < len(data) and data[p:p + 2] == b"\0\0":
            p += 2
        end = p
        while end < len(data) and data[end:end + 2] != b"\0\0":
            end += 2
        value = data[p:end].decode("utf-16-le", "replace").strip()
        if re.fullmatch(r"\d+(\.\d+)+.*", value):
            return value
