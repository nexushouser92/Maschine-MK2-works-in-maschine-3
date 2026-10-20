"""Tests for patch_mk2.py on small synthetic PE files: no Native Instruments binary is needed.

Run with: python -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import patch_mk2
from patch_mk2 import (ADD_DISTANCE, ADD_NEW, ADD_ORIG, JAM_TAIL, MOV_NEW, MOV_ORIG, apply, file_to_va,
                       file_version, identify, is_analyzed, sha256)

IMAGE_BASE, SECTION_VA, SECTION_RAW, SECTION_SIZE = 0x140000000, 0x1000, 0x400, 0x1C00
MOV_OFF = 0x1000
ADD_OFF = MOV_OFF - ADD_DISTANCE


def fake_exe(version="3.7.1", block=True):
    """Minimal PE32+ with one section, the Jam block at MOV_OFF and a FileVersion string."""
    d = bytearray(SECTION_RAW + SECTION_SIZE)
    d[0:2] = b"MZ"
    pe = 0x80
    d[0x3C:0x40] = pe.to_bytes(4, "little")
    d[pe:pe + 4] = b"PE\0\0"
    d[pe + 6:pe + 8] = (1).to_bytes(2, "little")         # NumberOfSections
    d[pe + 20:pe + 22] = (0xF0).to_bytes(2, "little")    # SizeOfOptionalHeader
    opt = pe + 24
    d[opt:opt + 2] = (0x20B).to_bytes(2, "little")       # PE32+
    d[opt + 24:opt + 32] = IMAGE_BASE.to_bytes(8, "little")
    s = opt + 0xF0
    d[s:s + 5] = b".text"
    d[s + 12:s + 16] = SECTION_VA.to_bytes(4, "little")
    d[s + 16:s + 20] = SECTION_SIZE.to_bytes(4, "little")
    d[s + 20:s + 24] = SECTION_RAW.to_bytes(4, "little")
    if block:
        d[ADD_OFF:ADD_OFF + len(ADD_ORIG)] = ADD_ORIG
        d[MOV_OFF:MOV_OFF + len(MOV_ORIG) + len(JAM_TAIL)] = MOV_ORIG + JAM_TAIL
    if version:
        res = "FileVersion".encode("utf-16-le") + b"\0\0" + b"\0\0" + version.encode("utf-16-le") + b"\0\0"
        d[0x1800:0x1800 + len(res)] = res
    return bytes(d)


def put(data, off, raw):
    d = bytearray(data)
    d[off:off + len(raw)] = raw
    return bytes(d)


class PatternTests(unittest.TestCase):
    def test_original_is_found(self):
        state, version, patches = identify(fake_exe())
        self.assertEqual((state, version), ("original", "3.7.1"))
        self.assertEqual([p[0] for p in patches], [ADD_OFF, MOV_OFF])
        self.assertFalse(is_analyzed(patches))

    def test_virtual_addresses(self):
        _, _, patches = identify(fake_exe())
        expected = [IMAGE_BASE + SECTION_VA + off - SECTION_RAW for off in (ADD_OFF, MOV_OFF)]
        self.assertEqual([p[1] for p in patches], expected)

    def test_apply_then_revert_round_trips(self):
        original = fake_exe()
        _, _, patches = identify(original)
        patched, _ = apply(original, patches, revert=False)
        self.assertEqual(patched[ADD_OFF:ADD_OFF + 6], ADD_NEW)
        self.assertEqual(patched[MOV_OFF:MOV_OFF + 5], MOV_NEW)

        state, version, patches2 = identify(bytes(patched))
        self.assertEqual((state, version), ("patched", "3.7.1"))
        restored, _ = apply(bytes(patched), patches2, revert=True)
        self.assertEqual(bytes(restored), original)

    def test_rejects_duplicate_block(self):
        data = put(fake_exe(), 0x700, MOV_ORIG + JAM_TAIL)
        self.assertEqual(identify(data), (None, None, None))

    def test_rejects_half_patched(self):
        data = put(fake_exe(), ADD_OFF, ADD_NEW)  # ADD patched, MOV still original
        self.assertEqual(identify(data), (None, None, None))

    def test_rejects_slot_already_used(self):
        data = put(fake_exe(), 0x600, ADD_NEW)
        self.assertEqual(identify(data), (None, None, None))

    def test_rejects_wrong_add_distance(self):
        data = put(put(fake_exe(), ADD_OFF, b"\0" * 6), ADD_OFF - 8, ADD_ORIG)
        self.assertEqual(identify(data), (None, None, None))

    def test_rejects_maschine_2(self):
        self.assertEqual(identify(fake_exe(version="2.18.3")), (None, None, None))

    def test_rejects_missing_version(self):
        self.assertEqual(identify(fake_exe(version=None)), (None, None, None))

    def test_rejects_missing_block(self):
        self.assertEqual(identify(fake_exe(block=False)), (None, None, None))

    def test_rejects_non_pe(self):
        data = b"XX" + fake_exe()[2:]
        self.assertEqual(identify(data), (None, None, None))


class HelperTests(unittest.TestCase):
    def test_file_version(self):
        self.assertEqual(file_version(fake_exe(version="3.6.0")), "3.6.0")
        self.assertIsNone(file_version(fake_exe(version=None)))

    def test_file_to_va_outside_sections(self):
        self.assertIsNone(file_to_va(fake_exe(), 0x10))

    def test_apply_mismatch_changes_nothing(self):
        data = fake_exe()
        _, _, patches = identify(data)
        out, err = apply(data, patches, revert=True)  # nothing is patched yet
        self.assertIsNone(out)
        self.assertIn("expected", err)


class KnownVersionTests(unittest.TestCase):
    def setUp(self):
        self.data = fake_exe()
        self.patches = [
            (ADD_OFF, 0x1, ADD_ORIG, ADD_NEW, "add"),
            (MOV_OFF, 0x2, MOV_ORIG, MOV_NEW, "mov"),
        ]
        self.saved = dict(patch_mk2.VERSIONS)
        patch_mk2.VERSIONS[sha256(self.data)] = ("9.9.9", self.patches)

    def tearDown(self):
        patch_mk2.VERSIONS.clear()
        patch_mk2.VERSIONS.update(self.saved)

    def test_known_hash_uses_analyzed_table(self):
        state, version, patches = identify(self.data)
        self.assertEqual((state, version), ("original", "9.9.9"))
        self.assertTrue(is_analyzed(patches))

    def test_known_hash_patched_is_recognized(self):
        patched, _ = apply(self.data, self.patches, revert=False)
        state, version, patches = identify(bytes(patched))
        self.assertEqual((state, version), ("patched", "9.9.9"))
        self.assertTrue(is_analyzed(patches))


if __name__ == "__main__":
    unittest.main()
