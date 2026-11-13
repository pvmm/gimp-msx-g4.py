# AGENTS.md — gimp-msx-g4.py workspace

## Goal

GIMP plug-ins that export an image as an MSX2 bitmap: **SCREEN 5** (GRAPHIC 4)
and **SCREEN 7** (GRAPHIC 6), optionally **interlaced** (double vertical
resolution, 424 lines).

## Files

| Path | What it is |
|---|---|
| `gimp2_msx_g4.py` | Plug-in for GIMP 2.10 (`gimpfu`/`gimp` API, PDB parameters). |
| `gimp3_msx_g4.py` | Plug-in for GIMP 3 (`gi`/Gimp 3 API, hand made GTK dialog). |
| `README.md` | User documentation: options, file formats, BASIC loaders. |
| `TODO.md` | Feature wishlist (all items done so far are checked). |
| `images/screen7i.png` | Sample interlaced SCREEN 7 image (512×424) used by `tests/test_screen7i.py`. |
| `samples/` | Sample MSX-BASIC loaders (e.g. interlaced SCREEN 7 split files `S70/S71`, `R70/R71`). |
| `notes/msx-formats.md` | **Reference**: MSX screen modes, VRAM layout and the file formats produced here. Read before changing any layout. |
| `tests/` | Offline tests + an optional openMSX based verifier (see `tests/README.md`). |

## The two plug-ins must stay in sync

`gimp2_msx_g4.py` and `gimp3_msx_g4.py` implement the same feature set and must
produce **byte identical** files. They are kept in sync by hand (the history
has several "synchronize both versions" commits), so:

* change the algorithm in one file and mirror it in the other;
* run `python3 tests/cmp_plugins.py` afterwards — it exports every
  encoding/screen-mode combination with both plug-ins and compares the SHA-256
  of every produced file.

Differences that used to exist and are now gone (do not reintroduce them):

* the GIMP 3 plug-in shifted the pixel indices by one when "reserve index 0"
  was enabled but the image had no transparency, while writing the palette
  from index 0 — the colours were off by one. Both plug-ins now offset the
  indices only when transparency is really used.
* the BSAVE end address was `size` instead of `size - 1` (MSX expects the last
  valid address).

## Conventions

* Screen dependent values live in `SCREEN_MODES` (width, bytes per line, page
  size, palette offset, file name suffix). Do not sprinkle `0x7680`/`0x8000`
  literals around.
* The encoding is stored as a base name (`SC`, `SR`, `DAT`, `RAW`); the file
  extension is `base + screen suffix` (`SC5`, `SC7`, `SR5`, `SR7`).
* Interlaced output: even lines in page 0, odd lines in page 1. `SC`/`SR` keep
  the pages apart (32K for SCREEN 5, 64K for SCREEN 7). Interlaced SCREEN 5 is
  a single 64K file; interlaced SCREEN 7 is split into two 64K files because it
  does not fit in one BSAVE: `S70`/`S71` (SC, with palette in page 0) and
  `R70`/`R71` (SR). `RAW`/`DAT` pack both pages together.
* The palette of a SCREEN 5 file lives at `0x7680`, of a SCREEN 7 file at
  `0xFA80`; the `.PAL` file uses the same offset.
* Comments are in English, code style is plain and procedural (no classes
  beyond the plug-in itself).

## Testing

Everything can be tested **without GIMP** — the plug-ins are plain Python and
the conversion code is extracted from the source with a stubbed `gi`/`gimpfu`:

```
python3 tests/test_g4.py          # GIMP 3 plug-in output, byte level checks
python3 tests/test_g4_gimp2.py    # GIMP 2 plug-in output
python3 tests/cmp_plugins.py      # both plug-ins must agree
python3 tests/test_screen7i.py    # real interlaced SCREEN 7 image (needs Pillow)
```

`tests/test_screen7i.py` converts `images/screen7i.png` (512×424, interlaced
SCREEN 7) and verifies: the export is split into `S70`/`S71` (one 64K page
each, `0000..FFFF`, palette at `0xFA80` in `S70`), page 0 holds the even
source lines and page 1 the odd source lines (decoding/interlacing
reconstructs the full image), and both plug-ins produce identical files for it.

`tests/verify_with_openmsx.py` is an optional end-to-end check that loads the
exported files into a headless openMSX instance and compares them with the
emulated screen (needs `openmsx` and a display; it takes a few minutes).

## MSX background you need

* A page is 32K (SCREEN 5) or 64K (SCREEN 7) and holds 256 lines; the VDP
  shows 212 of them (the `LN` bit of R#9).
* Interlaced mode (`IL` bit of R#9) shows 424 lines: the even field comes from
  the even page, the odd field from the odd page (32K/64K apart). The source
  image must therefore have twice the lines of the target screen.
* The `.SC5`/`.SC7` files are plain BSAVE files (0xFE header) and are loaded
  with `BLOAD "NONAME.SC5",S`; the palette is applied with `COLOR=RESTORE`.
* Details and references: `notes/msx-formats.md`.

## Gotchas found the hard way

* **openMSX's VRAM debug commands are not the programmer's view in GRAPHIC 6/7
  mode.** `vpoke`, `vpeek` and `save_msx_screen` work on the physical VRAM,
  whose bytes are interleaved by even/odd address between the four VRAM
  chips: writing a byte also changes its neighbour, so a pair of bytes can
  only carry one value. Never use them to check a bitmap layout —
  `tests/verify_with_openmsx.py` writes the data in decreasing pair order and
  reports which interpretation matches.
* What the emulator showed when the layouts were verified:
  * the exported SCREEN 7 bitmap appears on the emulated screen at the very
    same addresses → the bitmap is linear;
  * in interlaced mode the odd lines are found 32kB after the even ones
    (SCREEN 5) → the two pages are 32kB/64kB apart, as implemented here.
* openMSX's own screen dump (`save_msx_screen`) writes the bitmap
  **linearly**, 256 bytes per line for SCREEN 7, and dumps the interlaced
  screen as two files (`.SC5`/`.S1`, one per page) — that is the reference
  for the layouts used here.
* MSX-BASIC refuses `SCREEN 7` on some emulated machines even with 128kB of
  VRAM; set the VDP registers directly (`vdpreg`) when a test needs the mode.
* The emulated machine needs ~12s to boot before the VDP registers stick;
  setting them earlier is silently overwritten by the BIOS.
