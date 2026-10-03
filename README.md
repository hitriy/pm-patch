# Pocket Master English UI — one-byte patch

Switch a Chinese Sonicake Pocket Master to its built-in English UI by changing **one code byte** of the official firmware. The patcher also recalculates the firmware checksums. No translations or UI resources are replaced.

**Tested on a real Chinese Pocket Master with firmware V1.3.3: English UI confirmed working.**

## What you need

- The original **Pocket Master Firmware V1.3.3.bin** update file.
- [Python 3.8 or newer](https://www.python.org/downloads/).
- **Sonicake Manager** to install the patched firmware.

> **macOS checksum fix:** older patched files kept stale checksums and were rejected by the macOS updater. This patcher repairs all HTFW section and whole-file CRCs. Regenerate the update from your original firmware. CRC correctness is verified; flashing the corrected file on macOS still needs device confirmation. The English code patch was already tested using Windows.

## Patch and install

1. Download this repository using **Code → Download ZIP**, then extract it.
2. Put your original `Pocket Master Firmware V1.3.3.bin` in the extracted folder.
3. Open a terminal in that folder and run:

   ```powershell
   python patch_english.py "Pocket Master Firmware V1.3.3.bin"
   ```

4. In **Sonicake Manager**, select the generated file:

   ```text
   Pocket Master Firmware V1.3.3_English_1byte.bin
   ```

5. Install the update, reboot the pedal, and enjoy the English menus.

The original file is kept untouched. The script checks that you have the exact supported firmware and refuses unknown versions, previously modified files, or overwriting an existing output. If it rejects your file, start with a fresh original V1.3.3 update—do not use the older block-copy patch as input.

Keep your original firmware and do not disconnect the pedal during the update. Firmware files are not included in this repository.

The older `patch_en_block.py` remains available for reference; use `patch_english.py` for the one-byte patch.

[Technical details, Ghidra analysis, and earlier research →](docs/technical-analysis.md)
