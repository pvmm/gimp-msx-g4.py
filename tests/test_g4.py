#!/usr/bin/env python3
"""Offline tests for the GIMP 3 plug-in (gimp3_msx_g4.py).

The plug-in cannot be imported here (it needs GIMP's `gi` bindings), so the
pure-python conversion code is extracted from the source and executed with a
stubbed GLib. The produced files are then checked byte by byte against the
expected MSX formats (see notes/msx-formats.md).

Usage:  python3 tests/test_g4.py
"""
import os
import shutil
import struct
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.join(os.path.dirname(HERE), "gimp3_msx_g4.py")


def load_plugin():
    """Return the plug-in module with the GIMP specific parts stripped."""
    src = open(PLUGIN).read()
    # keep everything but the GIMP plug-in class and the gi imports
    src = src.split("class Graph4Exporter")[0]
    for line in ("import gi\n",
                 "gi.require_version('Gimp', '3.0')\n",
                 "from gi.repository import Gimp\n",
                 "gi.require_version('GimpUi', '3.0')\n",
                 "from gi.repository import GimpUi\n",
                 "gi.require_version('Gegl', '0.4')\n",
                 "from gi.repository import Gegl\n",
                 "from gi.repository import GObject\n",
                 "from gi.repository import GLib\n",
                 "from gi.repository import Gio\n"):
        src = src.replace(line, "")
    mod = types.ModuleType("plugin")
    mod.__dict__["GLib"] = types.SimpleNamespace(dgettext=lambda domain, msg: msg)
    exec(compile(src, PLUGIN, "exec"), mod.__dict__)
    return mod


class FakeConnector:
    """Stand-in for the plug-in's PluginConnector."""

    def __init__(self, width, height, pixels=None):
        self.width = width
        self.height = height
        if pixels is None:
            pixels = [(0, 0, 0, 255)] * (width * height)
        self.buffer = list(pixels)

    def set_progress(self, fraction=0.0, text=None, status=None):
        pass

    def set_pixel(self, x, y, pixel):
        self.buffer[x + y * self.width] = (pixel[0], pixel[1], pixel[2], 255)

    def get_pixel(self, x, y):
        return self.buffer[x + y * self.width]

    def throw(self, e):
        raise e


def make_image(width, height):
    """Image where every pixel has its own color."""
    px = []
    for y in range(height):
        for x in range(width):
            px.append((x * 7 % 256, y * 3 % 256, (x + y) % 256, 255))
    return px


def run(mod, outdir, encoding, screen_mode="SCREEN5", interlaced=False,
        width=256, height=212, dithering=0):
    """Convert an image and return the {name: path} of the produced files."""
    for f in os.listdir(outdir):
        os.remove(os.path.join(outdir, f))
    conn = FakeConnector(width, height, make_image(width, height))
    mod.do_convert(conn, "NONAME", outdir, dithering, 1, 1,
                   (255, 0, 255, 255), encoding, 1, screen_mode, interlaced)
    return {f: os.path.join(outdir, f) for f in sorted(os.listdir(outdir))}


def header(data):
    """Return the (start, end, exec) addresses of a BSAVE file."""
    return struct.unpack("<HHH", data[1:7])


def main():
    mod = load_plugin()
    outdir = tempfile.mkdtemp(prefix="msx-g4-test-")
    ok = True

    def check(cond, msg):
        nonlocal ok
        print(("  OK   " if cond else "  FAIL ") + msg)
        if not cond:
            ok = False

    try:
        # ------------------------------------------------------------- SC5
        print("SCREEN 5, binary with palette (SC5)")
        files = run(mod, outdir, "SC")
        check(list(files) == ["NONAME.PAL", "NONAME.SC5", "NONAME.TXT"],
              "files: %s" % list(files))
        data = open(files["NONAME.SC5"], "rb").read()
        check(data[0] == 0xFE, "binary prefix")
        check(header(data) == (0x0000, 0x769F, 0x0000),
              "header start/end/exec = %04X/%04X/%04X" % header(data))
        check(len(data) == 7 + 0x76A0, "file size = %d" % len(data))
        pal = open(files["NONAME.PAL"], "rb").read()
        check(header(pal)[:2] == (0x7680, 0x769F),
              "PAL header = %04X..%04X" % header(pal)[:2])
        check(pal[7:] == data[7 + 0x7680:7 + 0x76A0],
              "PAL file matches the embedded palette")
        # 2 pixels per byte, high nibble = even x
        for (x, y) in [(0, 0), (1, 0), (2, 0), (255, 0), (0, 1), (255, 211)]:
            byte = data[7 + (x // 2) + y * 128]
            nib = (byte >> 4) if x % 2 == 0 else (byte & 0x0F)
            check(nib != 0, "pixel (%d,%d) uses a non zero palette index" % (x, y))

        # ------------------------------------------------------------- SR5
        print("SCREEN 5, binary without palette (SR5)")
        files = run(mod, outdir, "SR")
        check("NONAME.SR5" in files, "files: %s" % list(files))
        data = open(files["NONAME.SR5"], "rb").read()
        check(header(data)[:2] == (0x0000, 0x69FF),
              "header = %04X..%04X" % header(data)[:2])
        check(len(data) == 7 + 128 * 212, "file size = %d" % len(data))

        # ------------------------------------------------------------- SC7
        print("SCREEN 7, binary with palette (SC7)")
        files = run(mod, outdir, "SC", screen_mode="SCREEN7", width=512, height=212)
        check(list(files) == ["NONAME.PAL", "NONAME.SC7", "NONAME.TXT"],
              "files: %s" % list(files))
        data = open(files["NONAME.SC7"], "rb").read()
        check(header(data)[:2] == (0x0000, 0xFA9F),
              "header = %04X..%04X" % header(data)[:2])
        check(len(data) == 7 + 0xFAA0, "file size = %d" % len(data))
        pal = open(files["NONAME.PAL"], "rb").read()
        check(header(pal)[:2] == (0xFA80, 0xFA9F),
              "PAL header = %04X..%04X" % header(pal)[:2])
        check(pal[7:] == data[7 + 0xFA80:7 + 0xFAA0],
              "PAL file matches the embedded palette")

        # ------------------------------------------------------------- SR7
        print("SCREEN 7, binary without palette (SR7)")
        files = run(mod, outdir, "SR", screen_mode="SCREEN7", width=512, height=212)
        data = open(files["NONAME.SR7"], "rb").read()
        check(header(data)[:2] == (0x0000, 0xD3FF),
              "header = %04X..%04X" % header(data)[:2])
        check(len(data) == 7 + 256 * 212, "file size = %d" % len(data))

        # ------------------------------------------------------- interlaced
        print("SCREEN 5, interlaced (2 x 32K pages)")
        files = run(mod, outdir, "SC", interlaced=True, width=256, height=424)
        data = open(files["NONAME.SC5"], "rb").read()
        check(header(data)[:2] == (0x0000, 0xFFFF),
              "header = %04X..%04X" % header(data)[:2])
        check(len(data) == 7 + 0x10000, "file size = %d (two 32K pages)" % len(data))
        check(data[7 + 0x8000] != 0, "page 1 holds the odd lines")
        check(data[7 + 0x8000 + 128] != 0, "page 1 line 1")
        check(data[7 + 0x7680:7 + 0x76A0] == open(files["NONAME.PAL"], "rb").read()[7:],
              "palette embedded in page 0")

        print("SCREEN 7, interlaced (2 x 64K pages, split files)")
        files = run(mod, outdir, "SC", screen_mode="SCREEN7", interlaced=True,
                    width=512, height=424)
        check(list(files) == ["NONAME.PAL", "NONAME.S70", "NONAME.S71", "NONAME.TXT"],
              "files: %s" % list(files))
        data0 = open(files["NONAME.S70"], "rb").read()
        data1 = open(files["NONAME.S71"], "rb").read()
        check(header(data0)[:2] == (0x0000, 0xFFFF),
              "S70 header = %04X..%04X" % header(data0)[:2])
        check(header(data1)[:2] == (0x0000, 0xFFFF),
              "S71 header = %04X..%04X" % header(data1)[:2])
        check(len(data0) == 7 + 0x10000, "S70 size = %d (page 0)" % len(data0))
        check(len(data1) == 7 + 0x10000, "S71 size = %d (page 1)" % len(data1))
        pal = open(files["NONAME.PAL"], "rb").read()
        check(data0[7 + 0xFA80:7 + 0xFAA0] == pal[7:],
              "palette embedded in page 0 (S70)")
        check(data1[7:] != data0[7:], "page 1 (S71) differs from page 0 (S70)")

        print("SCREEN 7, interlaced without palette (split files)")
        files = run(mod, outdir, "SR", screen_mode="SCREEN7", interlaced=True,
                    width=512, height=424)
        check(list(files) == ["NONAME.PAL", "NONAME.R70", "NONAME.R71", "NONAME.TXT"],
              "files: %s" % list(files))
        r0 = open(files["NONAME.R70"], "rb").read()
        r1 = open(files["NONAME.R71"], "rb").read()
        check(header(r0)[:2] == (0x0000, 0xFFFF), "R70 header = %04X..%04X" % header(r0)[:2])
        check(header(r1)[:2] == (0x0000, 0xFFFF), "R71 header = %04X..%04X" % header(r1)[:2])
        check(len(r0) == 7 + 0x10000 and len(r1) == 7 + 0x10000,
              "R70/R71 sizes = %d/%d" % (len(r0), len(r1)))

        print("SCREEN 5, interlaced raw file")
        files = run(mod, outdir, "RAW", interlaced=True, width=256, height=424)
        data = open(files["NONAME.RAW"], "rb").read()
        check(len(data) == 128 * 424, "file size = %d (packed, no page padding)" % len(data))
        half = len(data) // 2
        check(data[:half] != data[half:], "even and odd lines are packed separately")

        print("SCREEN 5, plain raw file")
        files = run(mod, outdir, "RAW", width=256, height=212)
        data = open(files["NONAME.RAW"], "rb").read()
        check(len(data) == 128 * 212, "file size = %d" % len(data))

        print("SCREEN 5, MSX-BASIC COPY format (DAT)")
        files = run(mod, outdir, "DAT", width=256, height=212)
        data = open(files["NONAME.DAT"], "rb").read()
        w, h = struct.unpack("<HH", data[0:4])
        check((w, h) == (256, 212), "header = %dx%d" % (w, h))
        check(len(data) == 4 + 128 * 212, "file size = %d" % len(data))

        # ----------------------------------------------------- size checks
        print("Size checks")
        try:
            run(mod, outdir, "SC", width=128, height=212)
            check(False, "wrong width should raise")
        except mod.ImageFormatError as e:
            check(True, "wrong width raises: %s" % e)
        try:
            run(mod, outdir, "SC", width=256, height=213, interlaced=True)
            check(False, "odd height should raise")
        except mod.ImageFormatError as e:
            check(True, "odd height raises: %s" % e)
        try:
            run(mod, outdir, "SC", width=256, height=257)
            check(False, "too tall should raise")
        except mod.ImageFormatError as e:
            check(True, "too tall raises: %s" % e)
    finally:
        shutil.rmtree(outdir, ignore_errors=True)

    print("\n%s" % ("ALL TESTS PASSED" if ok else "SOME TESTS FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
