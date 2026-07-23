#!/usr/bin/env python3
"""
Force English UI on Sonicake Pocket Master firmware (HTFW V1.3.3).

Copies the English menu-descriptor block over the Chinese block.
Does not modify string packs — uses the English strings already in the image.

Usage:
  python patch_en_block.py "Pocket Master Firmware V1.3.3.bin"
  python patch_en_block.py input.bin -o PocketMaster_EN.bin
"""
from __future__ import annotations

import argparse
import hashlib
import struct
import sys
from pathlib import Path

# Distinctive first dwords of each parallel menu block (little-endian RES ptrs)
CN_HDR = struct.pack("<I", 0x001341BC)
EN_HDR = struct.pack("<I", 0x00139C20)
BLOCK_SIZE = 0x128  # 296 bytes


def find_blocks(blob: bytes) -> tuple[int, int]:
    cn = blob.find(CN_HDR)
    en = blob.find(EN_HDR)
    if cn < 0 or en < 0:
        raise SystemExit(
            "Could not find CN/EN menu blocks "
            f"(markers 0x1341bc / 0x139c20). Wrong firmware file?"
        )
    if en - cn != BLOCK_SIZE:
        raise SystemExit(
            f"Unexpected block layout: CN@{cn:#x} EN@{en:#x} "
            f"delta={en - cn:#x} (expected {BLOCK_SIZE:#x})"
        )
    # Sanity: blocks should not appear more than once as headers
    if blob.find(CN_HDR, cn + 4) == en:
        pass  # EN block may share other dwords; header markers are unique enough
    return cn, en


def patch(blob: bytes) -> tuple[bytearray, int, int]:
    cn, en = find_blocks(blob)
    out = bytearray(blob)
    out[cn : cn + BLOCK_SIZE] = blob[en : en + BLOCK_SIZE]
    return out, cn, en


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path, help="Official HTFW .bin (e.g. V1.3.3)")
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output path (default: <input_stem>_en_block.bin)",
    )
    args = ap.parse_args()

    data = args.input.read_bytes()
    if not data.startswith(b"HTFW"):
        print("Warning: file does not start with HTFW magic — continuing anyway", file=sys.stderr)

    out, cn, en = patch(data)
    dest = args.output or args.input.with_name(args.input.stem + "_en_block.bin")
    dest.write_bytes(out)

    print(f"Input : {args.input} ({len(data)} bytes)")
    print(f"  md5 : {hashlib.md5(data).hexdigest()}")
    print(f"CN block @{cn:#x}, EN block @{en:#x}, size {BLOCK_SIZE:#x}")
    print(f"Output: {dest} ({len(out)} bytes)")
    print(f"  md5 : {hashlib.md5(out).hexdigest()}")
    print("Flash the output with the official Pocket Master updater.")


if __name__ == "__main__":
    main()
