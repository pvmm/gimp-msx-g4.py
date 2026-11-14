# MSX screen modes and file formats

Reference notes for the layouts implemented by this plug-in. Everything here
was cross-checked against primary sources and against openMSX.

## Sources

* **V9938 MSX-VIDEO Technical Data Book / Programmers Guide** (ASCII/Yamaha,
  1985) — the hardware reference. `map.grauw.nl/resources/video/v9938/`,
  `agelabs.pro/rs/Documentation/V9938-programmers-guide.pdf`.
* **MSX2 Technical Handbook** (Konami) — VRAM maps, interlace mode, the
  `SCREEN` statement parameters: `konamiman.github.io/MSX2-Technical-Handbook/`.
* **MSX Wiki** — `SCREEN_5`, `SCREEN_7`, `Screen Modes Description` pages.
* **Japanese MSX file format reference** (msxjpn.jimdofree.com) — the `.SC5`,
  `.SR5`, `.SC7`, `.SR7`, `.DAT` file layouts.
* **openMSX source** (`share/scripts/_save_msx_screen.tcl`,
  `src/video/DisplayMode.hh`, `src/video/VDP.cc`) — how a modern emulator
  writes and reads these formats.

## Screen modes

| | SCREEN 5 (GRAPHIC 4) | SCREEN 7 (GRAPHIC 6) |
|---|---|---|
| Resolution | 256x212 | 512x212 |
| Colors | 16 of 512 | 16 of 512 |
| Pixel data | 4 bits/pixel, 2 pixels per byte | 4 bits/pixel, 2 pixels per byte |
| Bytes per line | 128 | 256 |
| Bitmap size | 27136 bytes (212 lines) | 54272 bytes (212 lines) |
| Page size | 32K (256 lines) | 64K (256 lines) |
| Pages | 4 (0x00000, 0x08000, 0x10000, 0x18000) | 2 (0x00000, 0x10000) |
| Palette table | `0x7680`-`0x769F` | `0xFA80`-`0xFA9F` |
| Sprite tables | 0x7400/0x7600/0x7A00 | 0xF800/0xFA00/0xF000 |

The bitmap is **linear**: byte `y * bytes_per_line + x/2` holds the pixels
`x` (high nibble, even x) and `x+1` (low nibble). Line `y` of the second page
starts at `page_base + y * bytes_per_line`.

Only 212 of the 256 lines of a page are visible (the `LN` bit of R#9 selects
212 or 192 lines; the remaining lines of the page are never displayed).

The physical VRAM of a MSX2 is split over four 32kB chips; in GRAPHIC 6/7 the
chips hold the even and the odd bytes of the bitmap ("interleaved"). This is
invisible to the programmer (and to the renderer) — the bitmap is still
written and displayed linearly.

## Interlaced mode

R#9 bit 4 (`IL`) enables interlace: the frame has 424 lines instead of 212.
The even field displays the *even page* and the odd field the *odd page*
(R#9 bit 3 = `EO` selects the odd page address in R#2). Each field shows 212
lines, so a 424 line image is displayed: the even lines of the image in page
0, the odd lines in page 1.

* the pages are 32K apart in SCREEN 5 and 64K apart in SCREEN 7;
* the VDP alternates the two fields 60 times per second.

So an interlaced export needs a source image with twice the lines of the
target screen (e.g. 256x424 for a 256x212 SCREEN 5 screen), and the export
writes the even lines in page 0 and the odd lines in page 1.

openMSX dumps an interlaced screen as two files (`.SC5` and `.S15` — the mode
number is appended to the extension, one file per page). This plug-in keeps
both pages in a single file for SCREEN 5 and for `DAT` formats; interlaced
SCREEN 7 SC/SR is split into two files (`.S70`/`.S71`, `.R70`/`.R71`) because
two 64K pages do not fit in one BSAVE file, and interlaced SCREEN 7 RAW is
split into `w70`/`w71` (one raw page per file). Interlaced SCREEN 5 RAW packs
both pages together in a single `.RAW` file.

## File formats

All binary formats are BSAVE files: `0xFE`, start address (2 bytes), end
address (2 bytes, **inclusive**), execution address (2 bytes), then the data.
`BLOAD "FILE",S` loads the data at the start address (VRAM 0x0000 for the
files produced here).

### `.SC5` / `.SC7` — binary with palette

```
0x0000  bitmap (27136 bytes for SC5, 54272 for SC7)
0x6A00  unused
0x7680  palette (32 bytes)          <- SC5
0xD400  unused
0xFA80  palette (32 bytes)          <- SC7
```

End address: `0x769F` (SC5), `0xFA9F` (SC7). The palette is stored as in the
V9938: byte 0 = `R << 4 | B` (R in bits 6-4, B in bits 2-0), byte 1 = `G` in
bits 2-0.

### `.SR5` / `.SR7` — binary without palette

Only the bitmap, no palette: end address `0x69FF` (SC5) / `0xD3FF` (SC7).

### Interlaced `.SC5` / `.SR5`

Same as the non-interlaced formats but with both pages in a single file: page 0
at the start, page 1 32K later. The palette (SC5) stays at `0x7680` inside page
0. End address `0xFFFF`.

### Interlaced SCREEN 7 split files (`.S70`/`.S71`, `.R70`/`.R71`)

Interlaced SCREEN 7 is 128kB (two 64K pages) and does not fit in the 16-bit
address range of a BSAVE file, so it is split into two 64K BSAVE files (both
with header `0000..FFFF`):

| File | Encoding | Content |
|---|---|---|
| `NONAME.S70` | SC (with palette) | Page 0 (even lines), palette at `0xFA80` |
| `NONAME.S71` | SC (with palette) | Page 1 (odd lines) |
| `NONAME.R70` | SR (no palette) | Page 0 (even lines) |
| `NONAME.R71` | SR (no palette) | Page 1 (odd lines) |

Page 0 is the even page and page 1 the odd page (32K apart in SCREEN 5, 64K
apart in SCREEN 7 VRAM).

### `.DAT` — MSX-BASIC `COPY` screen dump

Width (2 bytes), height (2 bytes), then the bitmap. Limited to the screen
size (212 lines per field).

### `.RAW` — raw bitmap

No header, just the bitmap. With interlacing on SCREEN 5 (and for `DAT`), the
even lines come first and the odd lines follow immediately (no page padding).
With interlacing on SCREEN 7, the export is split into two files: `NONAME.w70`
(page 0, even lines) and `NONAME.w71` (page 1, odd lines), each containing one
raw page (64K for SCREEN 7).

### `.PAL` — palette file

A BSAVE file whose data is the 32 palette bytes at the palette offset
(`0x7680` / `0xFA80`). Load it with `BLOAD "NONAME.PAL",S` and then
`COLOR=RESTORE` to copy it into the VDP palette registers.

### `.TXT` — plain text palette

Human readable list of the 16 palette entries as R,G,B triplets (0-7).

## How these layouts were verified

* The bitmap layouts come from the V9938 manual (the pattern name table
  listing) and from the MSX wiki's SCREEN 7 page (byte 0x100 = the pixels
  (0,1),(1,1) → 256 bytes per line, linear).
* The file layouts come from the Japanese MSX file format reference and from
  openMSX's `share/scripts/_save_msx_screen.tcl`, which dumps SCREEN 5/7
  bitmaps linearly and splits an interlaced screen into two pages (`.SC5` and
  `.S15`/`.S17` — the mode number is appended, one file per page) that are 32kB
  apart in SCREEN 5 and 64kB apart in SCREEN 7.
* `tests/verify_with_openmsx.py` loads the exported files into a headless
  openMSX instance and compares them with the emulated screen (see the caveat
  about openMSX's VRAM debug commands in `AGENTS.md`).
* `tests/test_screen7i.py` converts the real interlaced SCREEN 7 sample image
  `images/screen7i.png` (512×424): the exported files are `NONAME.S70` and
  `NONAME.S71` (one 64K page each, header `0000..FFFF`), the palette at
  `0xFA80` in `S70`, page 0 = even lines, page 1 = odd lines, and
  decoding/interlacing the two fields reconstructs the full image. Both
  plug-ins produce identical files for it.

## BASIC loaders

### SCREEN 5 / SCREEN 7 (non-interlaced)

```
10 SCREEN 5                     ' or SCREEN 7
20 BLOAD"NONAME.SC5",S          ' or NONAME.SC7
30 COLOR=RESTORE
40 IF INKEY$="" GOTO 40
```

### Interlaced SCREEN 5

```
10 SCREEN 5
20 BLOAD"NONAME.SC5",S
30 COLOR=RESTORE
40 VDP(9)=VDP(9) OR &H0C        ' IL (interlace) + EO (even/odd pages)
50 IF INKEY$="" GOTO 50
```

### Interlaced SCREEN 7 (split files)

Interlaced SCREEN 7 is split into two 64K files (page 0 = even lines, page 1 = odd lines). Both pages must be loaded into VRAM (128K VRAM required):

```
10 SCREEN 7
20 BLOAD"NONAME.S70",S          ' page 0 (even lines) + palette
30 COLOR=RESTORE
40 SET PAGE 1,1
50 BLOAD"NONAME.S71",S          ' page 1 (odd lines)
60 SET PAGE 0,0
70 VDP(9)=VDP(9) OR &H0C        ' IL (interlace) + EO (even/odd pages)
80 IF INKEY$="" GOTO 80
```

Without embedded palette (`R70`/`R71`):

```
10 SCREEN 7
20 BLOAD"NONAME.PAL",S
30 COLOR=RESTORE
40 BLOAD"NONAME.R70",S
50 SET PAGE 1,1
60 BLOAD"NONAME.R71",S
70 SET PAGE 0,0
80 VDP(9)=VDP(9) OR &H0C
90 IF INKEY$="" GOTO 90
```

The `SCREEN` statement also takes an interlace parameter (`SCREEN 5,,,,,3`),
but setting R#9 directly is what the MSX2 Technical Handbook example does.
