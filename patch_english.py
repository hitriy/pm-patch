#!/usr/bin/env python3
"""Force English UI in the supported Pocket Master V1.3.3 HTFW update.

Changes one code byte and repairs HTFW checksums for checksum-enforcing
updaters, including macOS. Does not flash the device itself.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from htfw import repair_checksums, validate_checksums

INPUT_SHA256 = "d9112f12a37e3731e540b325d2b9788f005de7f640c129ac30465ea1dc57e7a3"
LEGACY_OUTPUT_SHA256 = "6a15c7501842f44f042baf84a542767cd6e87b335a3ceeb7ee9f8a189eec95a0"
OUTPUT_SHA256 = "13aebc913a39ce96858dd064b5dd30cccf477e545384486b47e18a84ea5fcaba"
FILE_SIZE = 2_056_820
PATCH_OFFSET = 0x631D9
CONTEXT_OFFSET = 0x631D8
ORIGINAL_CONTEXT = bytes.fromhex("e602e9034a0078203e074d54dd9e")


def patch(data: bytes) -> bytes:
    """Return the English code patch with valid CRCs, rejecting unknown input."""
    digest = hashlib.sha256(data).hexdigest()
    if digest in (OUTPUT_SHA256, LEGACY_OUTPUT_SHA256):
        raise ValueError("This firmware already has the one-byte English patch. Start from the original firmware.")
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
    validate_checksums(data)
    result = bytearray(data)
    result[PATCH_OFFSET] = 0x01  # slti45 a0,2 -> slti45 a0,1: accept English only.
    result = repair_checksums(result)
    validate_checksums(result)
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
    print("Verified: one code byte changed (0x631D9: 02 -> 01), plus HTFW checksum fields.")
    print("All section and whole-file CRCs are valid.")
    print("Install with Sonicake Manager. macOS device testing is still pending.")


if __name__ == "__main__":
    main()
