#!/usr/bin/env python3
"""Force English UI in the supported Pocket Master V1.3.3 HTFW update.

Changes one code byte. Flash with Sonicake Manager on Windows; the macOS
updater rejects the unchanged checksums. Does not flash the device itself.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

INPUT_SHA256 = "d9112f12a37e3731e540b325d2b9788f005de7f640c129ac30465ea1dc57e7a3"
OUTPUT_SHA256 = "6a15c7501842f44f042baf84a542767cd6e87b335a3ceeb7ee9f8a189eec95a0"
FILE_SIZE = 2_056_820
PATCH_OFFSET = 0x631D9
CONTEXT_OFFSET = 0x631D8
ORIGINAL_CONTEXT = bytes.fromhex("e602e9034a0078203e074d54dd9e")


def patch(data: bytes) -> bytes:
    """Return the exact tested one-byte patch, or reject unsupported input."""
    digest = hashlib.sha256(data).hexdigest()
    if digest == OUTPUT_SHA256:
        raise ValueError("This firmware already has the one-byte English patch.")
    if len(data) != FILE_SIZE or not data.startswith(b"HTFW"):
        raise ValueError("Expected the complete original V1.3.3 HTFW update file, not a raw dump.")
    if digest != INPUT_SHA256:
        raise ValueError(
            "Unsupported or modified firmware. Use the original Pocket Master Firmware "
            "V1.3.3.bin; older patched files cannot be used as input. "
            f"Input SHA-256: {digest}"
        )
    if data[CONTEXT_OFFSET:CONTEXT_OFFSET + len(ORIGINAL_CONTEXT)] != ORIGINAL_CONTEXT:
        raise ValueError("The language-selector instruction does not match.")
    result = bytearray(data)
    result[PATCH_OFFSET] = 0x01  # slti45 a0,2 -> slti45 a0,1: accept English only.
    if hashlib.sha256(result).hexdigest() != OUTPUT_SHA256:
        raise ValueError("Patched firmware verification failed; no output was written.")
    return bytes(result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Original Pocket Master Firmware V1.3.3.bin")
    parser.add_argument("-o", "--output", type=Path, help="Optional output filename")
    args = parser.parse_args()
    output = args.output or args.input.with_name(args.input.stem + "_English_1byte.bin")
    try:
        if output.resolve() == args.input.resolve():
            raise ValueError("The output must be different from the original file.")
        patched = patch(args.input.read_bytes())
        with output.open("xb") as stream:
            stream.write(patched)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    print(f"Created: {output}")
    print("Verified: exactly one byte changed (0x631D9: 02 -> 01).")
    print("Install this file with Sonicake Manager on Windows.")
    print("The macOS updater rejects the unchanged checksums.")


if __name__ == "__main__":
    main()
