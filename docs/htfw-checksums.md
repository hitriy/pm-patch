# HTFW checksum repair

The previous English patch changed code but left HTFW CRCs stale. Windows Sonicake Manager accepted it in the owner's test; the macOS updater rejected it. The new patcher recalculates the checksums while preserving the same device-tested language instruction change.

## Recovered algorithm

All five original section checksums and the encompassing file checksum match **CRC-16/MODBUS**:

- Width: 16 bits.
- Polynomial: `0x8005`, reflected implementation `0xA001`.
- Initial value: `0xFFFF`.
- Input/output reflection: true; final XOR: zero.
- Standard check vector: ASCII `123456789` gives `0x4B37`.
- **HTFW stores CRC values big-endian**, unlike the little-endian lengths and offsets. This is the container's storage convention, not Modbus wire byte order.

No macOS application binary was used to establish the algorithm. The evidence is agreement with all six stored CRCs in the exact supported original firmware, plus independent bitwise verification of the repaired file. Matching the format does not substitute for a macOS device test.

## Layout and coverage

For the supported V1.3.3 container:

| Offset | Meaning |
|---|---|
| `0x00` | `HTFW` magic |
| `0x04` | Big-endian 16-bit whole-file CRC over `[0x06, EOF)` |
| `0x08` | Little-endian 32-bit total file size |
| `0x22` | Little-endian 16-bit section count (5) |
| `0x24` | Little-endian 32-bit payload size |
| `0x38` | Section table, 16 bytes per entry |
| `0x88` | Payload starts after the five entries |

Each entry begins with a big-endian 16-bit CRC. The following two bytes are preserved metadata. At entry + 4 is a destination field; at + 8 is the little-endian payload-relative offset; at + 12 is the little-endian size. A section CRC covers exactly its payload bytes, excluding the descriptor.

| Descriptor offset | Payload-relative offset | Length | Original CRC |
|---|---|---|---|
| `0x38` | `0x000000` | `0x00C63C` | `0xBF94` |
| `0x48` | `0x00C63C` | `0x049050` | `0xA5F6` |
| `0x58` | `0x05568C` | `0x008000` | `0xFCD8` |
| `0x68` | `0x05D68C` | `0x15BB60` | `0x62EC` |
| `0x78` | `0x1B91EC` | `0x03D000` | `0xE079` |

The language instruction is in the fourth payload section. After patching, that section's CRC is `0x24C5`. Recompute section CRCs **before** the whole-file CRC, since the latter covers both the table and payload. The whole-file CRC changes from `0x24AC` to `0x967E`.

The parser validates the observed contiguous section layout and bounds. These findings do not establish a universal specification for every HTFW product/version. The public patcher continues to require the exact original firmware SHA-256.

## Exact output

Size remains 2,056,820 bytes. Differences from the supported original:

| File offset | Original | Patched |
|---|---|---|
| `0x04` | `24` | `96` |
| `0x05` | `AC` | `7E` |
| `0x68` | `62` | `24` |
| `0x69` | `EC` | `C5` |
| `0x631D9` | `02` | `01` |

Output SHA-256: `13aebc913a39ce96858dd064b5dd30cccf477e545384486b47e18a84ea5fcaba`.

Regenerate from the original file with `patch_english.py`; previously patched files are deliberately rejected. If the old default output exists, choose a new filename with `-o`. The script never overwrites an existing output.

## Validation

Public tests use synthetic two-section containers, the standard CRC check vector, independent bitwise fixture checksums, payload/header corruption, malformed bounds, and idempotent repair. Optional real-firmware tests independently verify all six original and output CRCs, the exact output digest, the five changed bytes, CLI behavior, and refusal of legacy patched input. No firmware is included in the repository.

The corrected artifact needs a macOS Sonicake Manager + pedal test before macOS flashing can be described as confirmed. Record the Manager version and the artifact hash when reporting that result.
