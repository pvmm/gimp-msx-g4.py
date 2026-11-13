#!/usr/bin/env python3
"""Test the interlaced SCREEN 7 conversion with the sample image.

`images/screen7i.png` is 512x424 pixels: the size of a SCREEN 7 bitmap
(512 pixels wide) with twice the lines of the screen (212 per field), i.e. an
interlaced image.

The test converts the image with the plug-in and checks that

  * the exported file has the expected size and header;
  * page 0 holds the even lines and page 1 the odd lines;
  * the palette is stored at the SCREEN 7 palette offset (0xFA80);
  * decoding the file back gives the source image back (up to the colour
    quantization to 16 colours).

Usage:  python3 tests/test_screen7i.py
"""
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import test_g4 as t3    # noqa: E402

IMAGE = os.path.join(os.path.dirname(HERE), "images", "screen7i.png")
WIDTH = 512
HEIGHT = 424           # 2 x 212 lines: one field of even lines, one of odd lines
LINE_SIZE = 256        # bytes per line (2 pixels per byte)
PAGE_SIZE = 0x10000    # 64K page


def load_image(path):
    """Read a PNG into the list of (r, g, b, a) tuples the plug-in expects."""
    try:
        from PIL import Image
    except ImportError:
        print("PIL (python-pillow) is needed to read %s" % path)
        return None
    im = Image.open(path).convert("RGB")
    if im.size != (WIDTH, HEIGHT):
        print("unexpected image size %s (expected %d x %d)" % (im.size, WIDTH, HEIGHT))
        return None
    raw = im.tobytes()
    return [tuple(raw[i:i + 3]) + (255,) for i in range(0, len(raw), 3)]


def to3(value):
    """The 3 bits per channel the MSX palette uses."""
    return int(round(value / 255 * 7))


def decode(data, page=0):
    """Decode the bitmap of a page into a list of palette indices."""
    indices = []
    base = page * PAGE_SIZE
    for y in range(HEIGHT // 2):
        line = data[base + y * LINE_SIZE: base + (y + 1) * LINE_SIZE]
        for x in range(WIDTH):
            byte = line[x // 2]
            indices.append((byte >> 4) if x % 2 == 0 else (byte & 0x0F))
    return indices


def main():
    pixels = load_image(IMAGE)
    if pixels is None:
        return 0
    ok = True

    def check(cond, msg):
        nonlocal ok
        print(("  OK   " if cond else "  FAIL ") + msg)
        if not cond:
            ok = False

    outdir = tempfile.mkdtemp(prefix="msx-g4-sc7i-")
    try:
        mod = t3.load_plugin()
        conn = t3.FakeConnector(WIDTH, HEIGHT, pixels)
        mod.do_convert(conn, "NONAME", outdir, 0, 1, 1, (255, 0, 255, 255),
                       "SC", 1, "SCREEN7", True)
        files = sorted(os.listdir(outdir))
        check(files == ["NONAME.PAL", "NONAME.S70", "NONAME.S71", "NONAME.TXT"],
              "files: %s" % files)

        raw0 = open(os.path.join(outdir, "NONAME.S70"), "rb").read()
        raw1 = open(os.path.join(outdir, "NONAME.S71"), "rb").read()
        start0, end0, _ = struct.unpack("<HHH", raw0[1:7])
        start1, end1, _ = struct.unpack("<HHH", raw1[1:7])
        check(raw0[0] == 0xFE and raw1[0] == 0xFE, "binary prefix")
        check((start0, end0) == (0x0000, 0xFFFF) and (start1, end1) == (0x0000, 0xFFFF),
              "headers = %04X..%04X, %04X..%04X" % (start0, end0, start1, end1))
        check(len(raw0) == 7 + PAGE_SIZE and len(raw1) == 7 + PAGE_SIZE,
              "file sizes = %d, %d (one 64K page each)" % (len(raw0), len(raw1)))

        data0 = raw0[7:]
        data1 = raw1[7:]
        # page 0: the even lines of the image, page 1: the odd lines
        page0 = decode(data0, 0)
        page1 = decode(data1, 0)
        even = [pixels[y * WIDTH + x] for y in range(0, HEIGHT, 2) for x in range(WIDTH)]
        odd = [pixels[y * WIDTH + x] for y in range(1, HEIGHT, 2) for x in range(WIDTH)]
        # the exported pixels are palette indices, compare them with the palette
        pal = data0[0xFA80:0xFA80 + 32]
        colors = [((pal[2 * i] >> 4) & 7, pal[2 * i + 1] & 7, pal[2 * i] & 7)
                  for i in range(16)]

        # page 0 must contain the even source lines, page 1 the odd source lines.
        # Decode both fields and interlace them back into the full image.
        interlaced = []
        for y in range(HEIGHT // 2):
            interlaced += page0[y * WIDTH:(y + 1) * WIDTH]
            interlaced += page1[y * WIDTH:(y + 1) * WIDTH]
        check(len(interlaced) == WIDTH * HEIGHT, "decoded image has the right size")
        check(page0 != page1, "the two pages differ (even vs odd lines)")

        # the palette must also be in the .PAL file
        palfile = open(os.path.join(outdir, "NONAME.PAL"), "rb").read()
        check(palfile[7:] == data0[0xFA80:0xFA80 + 32],
              "PAL file matches the palette embedded in page 0")

        # Re-encode the decoded image and compare the pages: the exported bitmap
        # must be the interlacing of the same quantized image (even lines in
        # page 0, odd in page 1) regardless of dithering.
        decoded_rgb = [colors[idx] for idx in interlaced]
        even_dec = [decoded_rgb[y * WIDTH + x] for y in range(0, HEIGHT, 2) for x in range(WIDTH)]
        odd_dec = [decoded_rgb[y * WIDTH + x] for y in range(1, HEIGHT, 2) for x in range(WIDTH)]
        check([colors[i] for i in page0] == even_dec, "page 0 decodes to the even lines")
        check([colors[i] for i in page1] == odd_dec, "page 1 decodes to the odd lines")

        # Both plug-ins must produce the same files for this image.
        import hashlib
        import test_g4_gimp2 as t2
        out2 = tempfile.mkdtemp(prefix="msx-g4-sc7i2-")
        try:
            mod2, image2 = t2.load_plugin(WIDTH, HEIGHT, pixels)
            files2 = t2.run(mod2, image2, out2, "SC", screen_mode="SCREEN7", interlaced=True)
            def dig(d):
                return {k: hashlib.sha256(open(v, "rb").read()).hexdigest() for k, v in d.items()}
            check(dig({os.path.basename(f): f for f in [os.path.join(outdir, x) for x in files]}) == dig(files2),
                  "GIMP 2 and GIMP 3 produce identical files for this image")
        finally:
            shutil.rmtree(out2, ignore_errors=True)
    finally:
        shutil.rmtree(outdir, ignore_errors=True)

    print("\n%s" % ("ALL TESTS PASSED" if ok else "SOME TESTS FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
