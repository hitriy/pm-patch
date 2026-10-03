"""Checksum layout recovered from the supported Pocket Master HTFW update.

CRC-16/MODBUS (poly 0x8005, reflected 0xA001, init 0xFFFF,
xorout 0). CRC fields are big-endian; lengths and offsets are little-endian.
"""
import struct


def _crc_table():
    table = []
    for value in range(256):
        for _ in range(8):
            value = (value >> 1) ^ (0xA001 if value & 1 else 0)
        table.append(value)
    return tuple(table)


_TABLE = _crc_table()


def crc16(data):
    crc = 0xFFFF
    for value in data:
        crc = (crc >> 8) ^ _TABLE[(crc ^ value) & 0xFF]
    return crc


def _sections(data):
    if len(data) < 0x38 or data[:4] != b"HTFW":
        raise ValueError("Invalid HTFW header.")
    if struct.unpack_from("<I", data, 8)[0] != len(data):
        raise ValueError("HTFW file size does not match the header.")
    count = struct.unpack_from("<H", data, 0x22)[0]
    payload_start = 0x38 + count * 16
    if not count or payload_start > len(data):
        raise ValueError("Invalid HTFW section table.")
    if struct.unpack_from("<I", data, 0x24)[0] != len(data) - payload_start:
        raise ValueError("HTFW payload size does not match the header.")
    sections = []
    expected_offset = 0
    for entry in range(0x38, payload_start, 16):
        offset, size = struct.unpack_from("<II", data, entry + 8)
        start = payload_start + offset
        end = start + size
        if offset != expected_offset or not size or end > len(data):
            raise ValueError("Invalid HTFW section bounds or ordering.")
        sections.append((entry, start, end))
        expected_offset = offset + size
    if payload_start + expected_offset != len(data):
        raise ValueError("HTFW sections do not cover the payload.")
    return sections


def validate_checksums(data):
    sections = _sections(data)
    view = memoryview(data)
    for entry, start, end in sections:
        if int.from_bytes(data[entry:entry + 2], "big") != crc16(view[start:end]):
            raise ValueError(f"HTFW section checksum mismatch at 0x{entry:X}.")
    if int.from_bytes(data[4:6], "big") != crc16(view[6:]):
        raise ValueError("HTFW whole-file checksum mismatch.")


def repair_checksums(data):
    """Return a copy with section CRCs first, then the encompassing file CRC."""
    sections = _sections(data)
    result = bytearray(data)
    view = memoryview(result)
    for entry, start, end in sections:
        result[entry:entry + 2] = crc16(view[start:end]).to_bytes(2, "big")
    result[4:6] = crc16(view[6:]).to_bytes(2, "big")
    return bytes(result)
