> Historical notes: the current, device-tested one-byte patch is documented in [Technical analysis](technical-analysis.md). Some hypotheses and address mappings below were superseded by that investigation.

# Pocket Master English UI — Research Notes & DIY Patch

How we figured out that Sonicake **Pocket Master** (QME-10 / CQME-10) ships one bilingual firmware, why naive “translate the Chinese strings” patches produce broken English, and how a **296-byte block copy** forces the real English UI without distributing a patched image.

---

## 1. The problem

China-SKU units show a Chinese LCD UI. Global units show English. Hardware looks the same. The obvious questions:

1. Are there two different firmware images?
2. If not, what selects language?
3. Can a China unit be forced to English cleanly?

**Answer in short:** one image contains both languages. Selection is supposed to be a region/lang latch (OTP / config — still not fully located). For a practical English UI today, copy the firmware’s own English menu-descriptor block over the Chinese one.

---

## 2. What we tried first (and what went wrong)

### Early approaches

| Approach | Result |
|----------|--------|
| Diff “CN dump” vs “official English” HTFW | Same app payload (aside from HTFW header / packaging). Not two products. |
| Search SDK `Efuse_ReadData` / MMIO `0x40023000` | Driver present in SDK reference tree; **absent** from this binary. |
| Overwrite Chinese UTF-8 strings in place | Partially works; many strings don’t fit; glyphs/truncation look wrong. |
| Remap every pointer into the CN string pack to a “matching” EN string (`en_both_v3`) | LCD becomes English-ish, but **labels are wrong** (hand-built map: e.g. effect names → generic “Effects”). |

`v3` proved the string packs and pointer tables are live, but it is a **bad** English experience because it invents translations instead of using the firmware’s real English menu table.

### Lesson

Do not scrub or remap strings if the bilingual tables already exist. Force the firmware to **use the English tables**.

---

## 3. Firmware layout (enough to understand the patch)

MCU family: Andes NDS32 (MVSilicon BP1048-class). Official updater files are **HTFW** containers (`HTFW` magic at offset 0).

Two address views matter when reverse-engineering:

| View | Rule of thumb |
|------|----------------|
| **CODE** (app) | `file_offset ≈ CODE_VMA + 0x5D6CA` |
| **RES** (UI resources / LE32 string ptrs) | `file_offset ≈ RES_VMA + 0x48000` |

UI strings live in two UTF-8 packs (RES space):

| Pack | RES VMA | Role |
|------|---------|------|
| Chinese | `0xE1300` … | CN labels |
| English | `0xE15E0` … | EN labels (stride `0x2E0` from CN) |

Those packs are not “selected” by adding `lang * 0x2E0` in obvious immediates. Instead, the UI is driven by **descriptor blocks** full of little-endian pointers into the packs.

---

## 4. Breakthrough: dual menu blocks

At the end of the resource area sit two nearly parallel structures of size **`0x128` (296) bytes**:

| Block | RES VMA | First dword (LE) | Meaning |
|-------|---------|------------------|---------|
| **CN** | `0x16B0F8` | `0x001341BC` | CN-only header / callback |
| **EN** | `0x16B220` | `0x00139C20` | EN-only header / callback |

Properties that made this the real target:

- Most fields that differ are string pointers: CN block → CN pack, EN block → EN pack (`+0x2E0` where paired).
- Shared icon/asset pointers appear in **both**.
- **Every** LE32 into the CN pack range in the whole image sits inside this dual-block region (67 slots in the dump we used).
- Remapping those pointers changes live LCD text → the blocks are not dead data.

Oddity (still open for RE): nothing in the image holds an absolute constant for `0x16B0F8` / `0x16B220` (`sethi` / LE32 / BE32 all empty). Boot likely picks a block via a latch + loader/interpreter we have not named yet. For patching, we do not need that latch: we make the CN slot contain the EN block.

```
  … resources …
  ┌─────────────────────────┐  CN menu block (0x128)
  │ cbs + ptrs → CN strings │  ← device currently uses this
  └─────────────────────────┘
  ┌─────────────────────────┐  EN menu block (0x128)
  │ cbs + ptrs → EN strings │  ← copy this over the CN block
  └─────────────────────────┘
  …
```

---

## 5. Working solution mechanics

### What the patch does

On the **official** `Pocket Master Firmware V1.3.3.bin` HTFW:

1. Locate the CN block by its unique header dword `0x001341BC`.
2. Locate the EN block by `0x00139C20` (exactly `0x128` bytes later).
3. **Memcpy** the EN block over the CN block (296 bytes).
4. Leave string packs, CRC packaging, and everything else untouched.

On V1.3.3 those headers land at:

| | File offset |
|--|-------------|
| CN block | `0x1B87CC` |
| EN block | `0x1B88F4` |

(Dump images without the HTFW header use `0x1B30F8` / `0x1B3220` — same content, different packaging.)

### Why this works

The runtime path that paints menus reads the **first** of the two blocks (or a structure that still aliases the CN slot). After the copy, that slot contains English callbacks and English string pointers. The device draws the same English UI the global SKU was built with — including correct effect names, prompts, and spacing — because those strings were already in the firmware.

### Why this is better than `v3`

| | `en_both_v3` (bad) | `en_block` (good) |
|--|--------------------|-------------------|
| Method | Remap/overwrite CN strings | Use EN descriptor block as-is |
| Labels | Often wrong / truncated | Match real English UI |
| Risk to packs | High | None (packs unchanged) |
| Size of change | Many scattered edits | **296 consecutive bytes** |

---

## 6. DIY: patch the firmware yourself

Do **not** redistribute a patched binary. Patch locally from Sonicake’s official HTFW, then flash with their updater.

### Requirements

- Official **Pocket Master Firmware V1.3.3** HTFW `.bin` (starts with ASCII `HTFW`).
- Python 3.8+.
- The script `patch_en_block.py` (same folder as this article, or copy the script below).

### Steps

1. Install / obtain the official updater package and note the path to
   `Pocket Master Firmware V1.3.3.bin`.
2. Run:

```bash
python patch_en_block.py "Pocket Master Firmware V1.3.3.bin"
```

3. Output default name: `Pocket Master Firmware V1.3.3_en_block.bin`
   (or pass `-o my_en.bin`).
4. Point the official Pocket Master firmware updater at that output file and flash.
5. Reboot the pedal and check menus (Effects / Drum / Settings / prompts).

### Verify before flashing

The script prints CN/EN offsets and MD5s. On stock V1.3.3 you should see:

- CN block `@0x1b87cc`, EN `@0x1b88f4`, size `0x128`
- After patch, bytes at the CN offset equal the original EN block

Optional one-liner check:

```bash
python -c "p=open('Pocket Master Firmware V1.3.3_en_block.bin','rb').read(); o=open('Pocket Master Firmware V1.3.3.bin','rb').read(); assert p[0x1b87cc:0x1b87cc+0x128]==o[0x1b88f4:0x1b88f4+0x128]; print('OK')"
```

### Standalone script (reference)

The maintained copy is `fw/patch_en_block.py`. Core logic:

```python
import struct
from pathlib import Path

CN_HDR = struct.pack("<I", 0x001341BC)
EN_HDR = struct.pack("<I", 0x00139C20)
BLOCK_SIZE = 0x128

def patch_en_block(data: bytes) -> bytes:
    cn = data.find(CN_HDR)
    en = data.find(EN_HDR)
    if cn < 0 or en < 0 or en - cn != BLOCK_SIZE:
        raise ValueError("CN/EN menu blocks not found or unexpected layout")
    out = bytearray(data)
    out[cn : cn + BLOCK_SIZE] = data[en : en + BLOCK_SIZE]
    return bytes(out)

# Path("out.bin").write_bytes(patch_en_block(Path("in.bin").read_bytes()))
```

Markers are searched by content, so the same script works for the dump-style image as well as HTFW V1.3.3 (offsets differ; layout delta stays `0x128`).

---

## 7. Safety / caveats

- **Brick risk:** as with any firmware flash — use the official tool, don’t power-cycle mid-update, keep a known-good stock image.
- **Updater CRC:** this patch only rewrites 296 data bytes inside the payload. If a future updater starts enforcing a section CRC that we have not mirrored, the tool might reject the file; V1.3.3 accepted the block copy in practice.
- **Not a region unlock:** BT name strings (`CQME-10` / `QME-10`), OTP, and other SKU bits are untouched. This only forces the **LCD menu language path** that those dual blocks feed.
- **Lang latch still unknown:** the elegant fix is inverting the boot check that chooses CN vs EN. Until that is found, the block copy is the reliable user-facing fix.

---

## 8. Research timeline (compressed)

1. **Map the binary** — NDS32 BE code, LE data; dual CODE/RES bases; Ghidra + `nds32` objdump.
2. **Find UI strings** — CN/EN UTF-8 packs; confirm RES base `file − 0x48000`.
3. **Prove consumers** — LE32 pointer tables; smoke remap → LCD changes.
4. **Reject false flags** — font bank at `0x1A0000` / `gp−13924`; `#0x2E0` effect tables; SDK remind-sound `LanguageMode`.
5. **Find dual blocks** — CN/EN descriptors stride `0x128`; all CN pack ptrs live there.
6. **Fail to find latch** — no absolute xrefs to block bases; selector still open.
7. **Ship working UX patch** — memcpy EN→CN block; verified on device.

Internal RE scratchpad (addresses, scripts, open questions): `RE_NOTES.md`.

---

## 9. License / distribution

- Official firmware remains Sonicake’s. Patch **your own copy**; don’t upload patched HTFWs.
- This write-up and `patch_en_block.py` are for personal repair / accessibility (English UI on a bilingual image you already have).
