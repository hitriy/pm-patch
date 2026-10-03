import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import patch_english

SCRIPT = Path(patch_english.__file__)
FIRMWARE = os.environ.get("POCKET_MASTER_FIRMWARE")


class RejectionTests(unittest.TestCase):
    def test_raw_or_truncated_input_is_rejected(self):
        for data in (b"", b"HTFW", b"not an update"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                patch_english.patch(data)

    def test_unrecognized_full_container_is_rejected(self):
        data = b"HTFW" + bytes(patch_english.FILE_SIZE - 4)
        with self.assertRaisesRegex(ValueError, "Unsupported or modified"):
            patch_english.patch(data)

    def test_cli_failure_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / "unsupported.bin"
            dst = Path(temp) / "result.bin"
            src.write_bytes(b"HTFW")
            result = subprocess.run([sys.executable, str(SCRIPT), str(src), "-o", str(dst)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(dst.exists())
            self.assertEqual(src.read_bytes(), b"HTFW")

    def test_cli_refuses_input_as_output(self):
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / "original.bin"
            src.write_bytes(b"keep me")
            result = subprocess.run([sys.executable, str(SCRIPT), str(src), "-o", str(src)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"different from the original", result.stderr)
            self.assertEqual(src.read_bytes(), b"keep me")


@unittest.skipUnless(FIRMWARE, "Set POCKET_MASTER_FIRMWARE to test your original V1.3.3 update")
class FirmwareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = Path(FIRMWARE).read_bytes()

    def test_matches_checksum_corrected_output(self):
        result = patch_english.patch(self.original)
        self.assertEqual(len(result), len(self.original))
        self.assertEqual(hashlib.sha256(result).hexdigest(),
                         "13aebc913a39ce96858dd064b5dd30cccf477e545384486b47e18a84ea5fcaba")
        self.assertEqual([(i, a, b) for i, (a, b) in enumerate(zip(self.original, result)) if a != b],
                         [(4, 0x24, 0x96), (5, 0xAC, 0x7E),
                          (0x68, 0x62, 0x24), (0x69, 0xEC, 0xC5), (0x631D9, 2, 1)])

    def test_original_and_output_checksums_with_independent_implementation(self):
        from test_htfw import reference_crc
        import struct
        for data in (self.original, patch_english.patch(self.original)):
            self.assertEqual(reference_crc(data[6:]), int.from_bytes(data[4:6], "big"))
            for entry in range(0x38, 0x88, 16):
                offset, size = struct.unpack_from("<II", data, entry + 8)
                self.assertEqual(reference_crc(data[0x88 + offset:0x88 + offset + size]),
                                 int.from_bytes(data[entry:entry + 2], "big"))

    def test_legacy_patched_input_is_rejected(self):
        data = bytearray(self.original)
        data[patch_english.PATCH_OFFSET] = 1
        with self.assertRaisesRegex(ValueError, "already has"):
            patch_english.patch(data)

    def test_already_patched_input_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "already has"):
            patch_english.patch(patch_english.patch(self.original))

    def test_modified_original_is_rejected(self):
        damaged = bytearray(self.original)
        damaged[-1] ^= 1
        with self.assertRaisesRegex(ValueError, "Unsupported or modified"):
            patch_english.patch(bytes(damaged))

    def test_cli_default_output_and_refusal_to_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / "Pocket Master Firmware V1.3.3.bin"
            src.write_bytes(self.original)
            args = [sys.executable, str(SCRIPT), str(src)]
            result = subprocess.run(args, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            dst = src.with_name("Pocket Master Firmware V1.3.3_English_1byte.bin")
            self.assertEqual(dst.read_bytes(), patch_english.patch(self.original))
            dst.write_bytes(b"preserve existing output")
            result = subprocess.run(args, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(dst.read_bytes(), b"preserve existing output")
            self.assertEqual(src.read_bytes(), self.original)


if __name__ == "__main__":
    unittest.main()
