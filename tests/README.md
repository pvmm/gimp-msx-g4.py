# Tests

Everything here runs **without GIMP**: the plug-ins are plain Python, so the
conversion code is extracted from the source with a stubbed `gi`/`gimpfu` API
and the produced files are checked byte by byte.

```
python3 tests/test_g4.py          # GIMP 3 plug-in: file formats, sizes, headers
python3 tests/test_g4_gimp2.py    # GIMP 2 plug-in: same checks
python3 tests/cmp_plugins.py      # both plug-ins must produce identical files
```

All three exit with a non zero status when a check fails.

## What is checked

* `test_g4.py` / `test_g4_gimp2.py`
  * the BSAVE header (`0xFE`, start/end/exec addresses) and the file size of
    every format: `.SC5`, `.SR5`, `.SC7`, `.SR7`, `.DAT`, `.RAW`;
  * the palette position inside the file (`0x7680` for SCREEN 5, `0xFA80` for
    SCREEN 7) and that the `.PAL` file matches the embedded palette;
  * that two pixels share one byte (high nibble = even x);
  * the interlaced layout: two pages (32K for SCREEN 5, 64K for SCREEN 7) with
    the odd lines in page 1, and the packed (no page padding) raw variant;
  * the size validation (wrong width, odd height, too tall).
* `cmp_plugins.py` exports every encoding/screen mode combination with both
  plug-ins and compares the SHA-256 of every file.
* `test_screen7i.py` converts the sample interlaced SCREEN 7 image
  `images/screen7i.png` (512x424) and checks that the export is split into
  `NONAME.S70`/`NONAME.S71` (one 64K page each), that page 0 holds the even
  lines and page 1 the odd lines, that the palette is at `0xFA80` in `S70`,
  and that both plug-ins produce identical files for it.

## Optional: verify against a real V9938

`verify_with_openmsx.py` boots a headless openMSX instance (MSX2 with 128kB of
VRAM), writes an exported file into the emulated VRAM and compares the
emulated screen with the file:

```
python3 tests/verify_with_openmsx.py
```

Requirements: `openmsx` in `$PATH` and a working display. It takes a few
minutes (every byte is transferred through the emulator's control protocol).

It reports whether

* the SCREEN 7 bitmap shows up on the emulated screen at the same addresses as
  in the exported file (the bitmap is linear);
* in interlaced mode the two pages are 32kB apart (SCREEN 5) and hold the even
  and the odd lines of the image.

It is a *diagnostic* tool, not a pass/fail test: openMSX's VRAM debug commands
work on the physical VRAM, where the bytes of a pair share one value, so the
script accepts the pair-duplicated picture as well and says which
interpretation matched.

`omsx.py` is the small client for openMSX's XML control protocol used by that
script.
