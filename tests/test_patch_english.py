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

    def test_matches_device_tested_output_with_one_byte_difference(self):
        result = patch_english.patch(self.original)
        self.assertEqual(len(result), len(self.original))
        self.assertEqual(hashlib.sha256(result).hexdigest(),
                         "6a15c7501842f44f042baf84a542767cd6e87b335a3ceeb7ee9f8a189eec95a0")
        self.assertEqual([(i, a, b) for i, (a, b) in enumerate(zip(self.original, result)) if a != b],
                         [(0x631D9, 2, 1)])

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
