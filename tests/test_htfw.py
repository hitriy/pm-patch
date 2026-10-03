"""Synthetic fixtures require no proprietary firmware."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import htfw


def reference_crc(data):
    """Bitwise reference, independent of the production lookup table."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xA001 if crc & 1 else 0)
    return crc


def fixture():
    payloads = [b"first section", bytes(range(256))]
    header = bytearray(0x58)
    header[:4] = b"HTFW"
    struct.pack_into("<I", header, 8, len(header) + sum(map(len, payloads)))
    struct.pack_into("<H", header, 0x22, 2)
    struct.pack_into("<I", header, 0x24, sum(map(len, payloads)))
    offset = 0
    for i, payload in enumerate(payloads):
        entry = 0x38 + i * 16
        header[entry:entry + 2] = reference_crc(payload).to_bytes(2, "big")
        header[entry + 2:entry + 4] = b"\x00\x62"
        struct.pack_into("<III", header, entry + 4, i * 0x10000, offset, len(payload))
        offset += len(payload)
    result = header + b"".join(payloads)
    result[4:6] = reference_crc(result[6:]).to_bytes(2, "big")
    return bytes(result)


class ChecksumTests(unittest.TestCase):
    def test_standard_check_vector(self):
        self.assertEqual(htfw.crc16(b"123456789"), 0x4B37)
        self.assertEqual(htfw.crc16(b""), 0xFFFF)

    def test_original_is_valid_and_repair_is_idempotent(self):
        data = fixture()
        htfw.validate_checksums(data)
        self.assertEqual(htfw.repair_checksums(data), data)

    def test_payload_edit_updates_section_then_whole_file(self):
        original = fixture()
        edited = bytearray(original)
        edited[-1] ^= 1
        with self.assertRaisesRegex(ValueError, "section checksum"):
            htfw.validate_checksums(edited)
        repaired = htfw.repair_checksums(edited)
        htfw.validate_checksums(repaired)
        self.assertEqual(repaired[0x38:0x48], original[0x38:0x48])
        self.assertNotEqual(repaired[0x48:0x4A], original[0x48:0x4A])
        self.assertEqual(repaired[0x48:0x4A], reference_crc(repaired[0x65:]).to_bytes(2, "big"))
        self.assertEqual(repaired[4:6], reference_crc(repaired[6:]).to_bytes(2, "big"))
        self.assertEqual(repaired[0x58:], edited[0x58:])
        self.assertEqual(htfw.repair_checksums(repaired), repaired)

    def test_metadata_edit_requires_whole_file_crc(self):
        data = bytearray(fixture())
        data[0xC] ^= 1
        with self.assertRaisesRegex(ValueError, "whole-file"):
            htfw.validate_checksums(data)
        repaired = htfw.repair_checksums(data)
        self.assertEqual(repaired[6:], data[6:])
        htfw.validate_checksums(repaired)

    def test_corrupt_crc_fields_are_detected(self):
        for offset in (4, 0x38, 0x48):
            data = bytearray(fixture())
            data[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                htfw.validate_checksums(data)

    def test_malformed_layout_rejected(self):
        for offset, fmt, value in ((8, "<I", 0), (0x22, "<H", 0xFFFF),
                                   (0x24, "<I", 1), (0x40, "<I", 1),
                                   (0x44, "<I", 0xFFFFFFFF), (0x50, "<I", 0)):
            data = bytearray(fixture())
            struct.pack_into(fmt, data, offset, value)
            for action in (htfw.validate_checksums, htfw.repair_checksums):
                with self.subTest(offset=offset, action=action), self.assertRaises(ValueError):
                    action(data)
        for data in (b"", b"HTFW", b"NOPE" + fixture()[4:], fixture()[:-1]):
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                htfw.repair_checksums(data)
