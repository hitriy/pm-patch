# Technical analysis: one-byte English UI patch

The one-byte patch in `patch_english.py` was verified with Ghidra and then successfully flashed to a Chinese Pocket Master by its owner. The owner confirmed that it works on the pedal. This supersedes the older descriptor-block copy as the recommended method.

## Supported file and exact change

The patcher supports one complete, original V1.3.3 HTFW update, 2,056,820 bytes long:

| File | SHA-256 |
|---|---|
| Original | `d9112f12a37e3731e540b325d2b9788f005de7f640c129ac30465ea1dc57e7a3` |
| Patched, CRCs repaired | `13aebc913a39ce96858dd064b5dd30cccf477e545384486b47e18a84ea5fcaba` |
| Historical patch, stale CRCs (Windows device-tested) | `6a15c7501842f44f042baf84a542767cd6e87b335a3ceeb7ee9f8a189eec95a0` |

**Code change at file offset `0x631D9`: `02` → `01`.** The current patcher also updates two 16-bit CRC fields, making five changed bytes in total. Strings, menu descriptors, graphics and all other bytes remain unchanged. Both input and output hashes are checked by the script.

The Windows Sonicake software did not enforce these firmware checksums and was used for the successful flash of the historical patch. The macOS version rejected that stale-checksum file. The current patcher repairs the CRCs to address this rejection; actual flashing on macOS remains unverified. See [HTFW checksum research](htfw-checksums.md) for coverage, byte order and exact output differences.

## What selects the language

The relevant application runs on NDS32, with big-endian instruction encoding and little-endian data. The supplied firmware also contains code for another processor; disassembling the entire file as a single flat NDS32 program is misleading.

The NDS32 global pointer is `gp = 0x2000FA40`. The UI-language selector is one byte at `0x20004794` (`gp - 0xB2AC`). Its values are:

- `0`: English.
- `1`: Chinese.

Two functions consume this selector:

| Runtime address | Purpose |
|---|---|
| `0x15A9C` | Look up a localized text pointer |
| `0x15AB0` | Look up a localized image pointer |
| `0x15AC4` | Set the language index |

Both lookup functions select an eight-byte row from the table at RAM `0x20003900`:

| Index | Language | Text pointer array | Image pointer array |
|---:|---|---:|---:|
| 0 | English | `0x20003C30` | `0x20003C20` |
| 1 | Chinese | `0x20003B08` | `0x20003AF8` |

Each descriptor block contains four image pointers followed by 70 text pointers: `0x128` bytes total. These are the same English and Chinese blocks targeted by the previous working patch.

## The one-byte patch

The original setter accepts language indices below two:

```asm
00015ac4  e6 02        slti45 a0,0x2
00015ac6  e9 03        bnezs8 0x00015acc
00015ac8  4a 00 78 20  ret lp
00015acc  3e 07 4d 54  sbi.gp a0,[gp - 0xb2ac]
00015ad0  dd 9e        ret5 lp
```

Change `e6 02` to `e6 01`. The unsigned comparison becomes `requested < 1`. Only English, index zero, reaches the store; a Chinese request takes the return path.

The resulting behavior can be expressed as:

```c
void set_ui_language(uint32_t requested) {
    if (requested == 0)
        ui_language_index = 0;
}
```

This does not depend on uninitialized RAM. Startup at `0x626AC` clears BSS from `0x200045A0` through `0x2001BB87`, including the selector. It therefore starts at zero, and the patched setter can never change it to one. Both startup selection and later language-setting paths use this setter in the traced application.

The separate settings-language value and SKU identification are unchanged. A host/settings request can still report Chinese while the LCD resources remain English. This is an English UI patch, not a general international-SKU conversion.

## The hardware-variant decision

Ghidra also identified the initialization code at `0x4E58C`. Equivalent C:

```c
uint32_t variant = get_device_variant();
settings_language = (variant == 2);
set_ui_language(settings_language);
```

Relevant instructions:

```asm
0004e592  jal      0x000518d0
0004e596  subi45   a0,0x2
0004e598  slti     a1,a0,0x1
0004e59c  mov55    a0,a1
0004e59e  sbi.gp   a1,[gp - 0x2b4e]
0004e5a2  jal      0x00015ac4
```

`slti` uses an unsigned comparison, so `(variant - 2) < 1` is true only for variant two. The getter at `0x518D0` reads a pointer from RAM `0x20003EA8`, then loads the word at pointer + `0x15C`. The initialized pointer is `0x001E0000`, making the accessed runtime address `0x001E015C`. A neighboring configuration accessor checks a `0x5AFF` signature.

This identifies a configuration-field dependency. It does **not** establish an OTP bit or the physical backing of that address. Runtime addresses must not be treated as offsets into the updater file.

A separate one-byte alternative can change `slti a1,a0,1` to `slti a1,a0,0`, making initialization select English for every variant. The shared-setter patch was chosen because it also prevents later requests from selecting Chinese. Only the shared-setter patch is offered by the user-facing script and confirmed by the pedal test.

## Address mapping and why earlier searches missed it

The descriptor blocks are copied from the load image into SRAM, then accessed through the `gp`-relative table. Code does not need to contain the original flash block addresses as direct constants.

For the supported full HTFW file:

| Item | File offset | Runtime address |
|---|---:|---:|
| Language setter | `0x631D8` | `0x15AC4` |
| Patched byte | `0x631D9` | second byte of that instruction |
| CN descriptor | `0x1B87CC` | RAM `0x20003AF8` |
| EN descriptor | `0x1B88F4` | RAM `0x20003C20` |

The earlier investigation also used an extracted image, SHA-256 `9ae677008b15e80ba0a4eb35a06e99fc0d32cc2a371abf6ce54ba29182fe9237`. In that file, the patch byte is at `0x6318F`, and the descriptors are at `0x1B30F8` and `0x1B3220`. These offset differences are **not uniform across the file**. Do not use raw-image offsets on an HTFW update.

For that extracted image, the verified resource mapping is `file = VMA + 0x48040`, correcting the approximate `+0x48000` mapping in the historical notes. The CN and EN resource VMAs are `0x16B0B8` and `0x16B1E0`. Startup copies `0xCA0` bytes from resource VMA `0x16AEC0` to RAM `0x20003900`.

## Validation and tests

Ghidra disassembly and decompilation established the code path. Ghidra's emulator then checked:

- The original setter selects Chinese for argument one.
- The patched setter retains English for arguments `0`, `1`, `2`, `3`, `255`, `256`, `0x7FFFFFFF` and `0xFFFFFFFF`.
- All 70 English text pointers and all four English image pointers resolve through the original lookup functions.
- The separate initialization-comparison alternative produces zero for the tested variant values.

The historical full HTFW patch was checked against the analyzed instruction context and surrounding code. That output differed from the original at exactly one byte; the owner flashed it and confirmed the English UI works. The new output retains that code change and repairs the section and whole-file checksums. Tests verify its exact five-byte difference and independently recompute all CRCs. A device test of the checksum-corrected file on macOS is still pending.

Run the public tests without firmware:

```powershell
python -m unittest discover -s tests -v
```

To also test the exact supported update locally, provide your own original file:

```powershell
$env:POCKET_MASTER_FIRMWARE = "C:\path\Pocket Master Firmware V1.3.3.bin"
python -m unittest discover -s tests -v
```

Firmware binaries and Ghidra projects containing firmware bytes are not distributed in this repository.

## Earlier research

[Original block-copy investigation and previous approaches](legacy-research.md) — historical notes; use the addresses and one-byte method above for the current patch.
