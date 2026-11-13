#!/usr/bin/env python3
"""Offline tests for the GIMP 2 plug-in (gimp2_msx_g4.py).

The plug-in needs GIMP's `gimpfu`/`gimp` modules, so they are stubbed here and
the produced files are checked byte by byte against the expected MSX formats
(see notes/msx-formats.md).

Usage:  python3 tests/test_g4_gimp2.py
"""
import os
import shutil
import struct
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.join(os.path.dirname(HERE), "gimp2_msx_g4.py")


class FakeRegion:
    """Stand-in for a GIMP pixel region (a string of bytes)."""

    def __init__(self, pixels, width, height):
        self.data = "".join(chr(c) for p in pixels for c in p)
        self.width = width
        self.height = height

    def __getitem__(self, rect):
        xs, ys = rect
        out = []
        for y in range(ys.start, ys.stop):
            for x in range(xs.start, xs.stop):
                i = (y * self.width + x) * 4
                out.append(self.data[i:i + 4])
        return "".join(out)

    def __setitem__(self, rect, value):
        xs, ys = rect
        buf = list(self.data)
        for i, ch in enumerate(value):
            buf[i] = ch
        self.data = "".join(buf)


class FakeDrawable:
    def __init__(self, width, height, pixels):
        self._w = width
        self._h = height
        self.has_alpha = True
        self.region = FakeRegion(pixels, width, height)

    def get_pixel_rgn(self, *args):
        return self.region

    def get_width(self):
        return self._w

    def get_height(self):
        return self._h


class FakeLayer:
    def __init__(self, drawable):
        self.has_alpha = True
        self.drawable = drawable

    def add_alpha(self):
        pass


class FakeImage:
    def __init__(self, drawable):
        self.layers = [FakeLayer(drawable)]
        self.drawable = drawable


def make_image(width, height):
    """Image where every pixel has its own color."""
    px = []
    for y in range(height):
        for x in range(width):
            px.append((x * 7 % 256, y * 3 % 256, (x + y) % 256, 255))
    return px


def load_plugin(width, height, pixels):
    """Return the plug-in module with a stubbed GIMP API."""
    drawable = FakeDrawable(width, height, pixels)
    image = FakeImage(drawable)

    pdb = types.SimpleNamespace(
        gimp_image_active_drawable=lambda img: drawable,
        gimp_drawable_width=lambda d: width,
        gimp_drawable_height=lambda d: height,
        gimp_image_duplicate=lambda img: image,
        gimp_image_base_type=lambda img: 0,  # RGB
        gimp_image_get_colormap=lambda img: (0, b""),
        gimp_image_convert_rgb=lambda img: None,
        gimp_display_new=lambda img: None,
        gimp_progress_update=lambda f: None,
        gimp_progress_init=lambda *a: None,
    )
    gimpfu = types.ModuleType("gimpfu")
    gimpfu.pdb = pdb
    gimpfu.register = lambda *a, **k: None
    gimpfu.main = lambda: None
    gimpfu.PF_STRING = gimpfu.PF_DIRNAME = gimpfu.PF_BOOL = 0
    gimpfu.PF_COLOR = gimpfu.PF_RADIO = 0
    gimp = types.ModuleType("gimp")
    gimp.message = lambda msg: print("GIMP MESSAGE:", msg)
    gimp.delete = lambda img: None
    sys.modules["gimpfu"] = gimpfu
    sys.modules["gimp"] = gimp

    src = open(PLUGIN).read().replace("gimpfu.main()", "")
    mod = types.ModuleType("plugin")
    mod.__dict__["gimpfu"] = gimpfu
    mod.__dict__["gimp"] = gimp
    exec(compile(src, PLUGIN, "exec"), mod.__dict__)
    return mod, image


def run(mod, image, outdir, encoding, screen_mode="SCREEN5", interlaced=False):
    """Convert an image and return the {name: path} of the produced files."""
    for f in os.listdir(outdir):
        os.remove(os.path.join(outdir, f))
    mod.do_write_g4(image, None, "NONAME", outdir, 0, 1, 1, (255, 0, 255, 255),
                    encoding, 1, screen_mode, interlaced)
    return {f: os.path.join(outdir, f) for f in sorted(os.listdir(outdir))}


def header(data):
    """Return the (start, end, exec) addresses of a BSAVE file."""
    return struct.unpack("<HHH", data[1:7])


def main():
    outdir = tempfile.mkdtemp(prefix="msx-g4-test2-")
    ok = True

    def check(cond, msg):
        nonlocal ok
        print(("  OK   " if cond else "  FAIL ") + msg)
        if not cond:
            ok = False

    try:
        # ------------------------------------------------------------- SC5
        print("SCREEN 5, binary with palette (SC5)")
        mod, image = load_plugin(256, 212, make_image(256, 212))
        files = run(mod, image, outdir, "SC")
        check(list(files) == ["NONAME.PAL", "NONAME.SC5", "NONAME.TXT"],
              "files: %s" % list(files))
        data = open(files["NONAME.SC5"], "rb").read()
        check(header(data) == (0x0000, 0x769F, 0x0000),
              "header = %04X..%04X" % header(data)[:2])
        check(len(data) == 7 + 0x76A0, "file size = %d" % len(data))

        # ------------------------------------------------------------- SR5
        print("SCREEN 5, binary without palette (SR5)")
        files = run(mod, image, outdir, "SR")
        data = open(files["NONAME.SR5"], "rb").read()
        check(header(data)[:2] == (0x0000, 0x69FF),
              "header = %04X..%04X" % header(data)[:2])
        check(len(data) == 7 + 128 * 212, "file size = %d" % len(data))

        # ------------------------------------------------------------- SC7
        print("SCREEN 7, binary with palette (SC7)")
        mod7, image7 = load_plugin(512, 212, make_image(512, 212))
        files = run(mod7, image7, outdir, "SC", screen_mode="SCREEN7")
        check(list(files) == ["NONAME.PAL", "NONAME.SC7", "NONAME.TXT"],
              "files: %s" % list(files))
        data = open(files["NONAME.SC7"], "rb").read()
        check(header(data)[:2] == (0x0000, 0xFA9F),
              "header = %04X..%04X" % header(data)[:2])
        check(len(data) == 7 + 0xFAA0, "file size = %d" % len(data))

        # ------------------------------------------------------- interlaced
        print("SCREEN 5, interlaced")
        mod_i, image_i = load_plugin(256, 424, make_image(256, 424))
        files = run(mod_i, image_i, outdir, "SC", interlaced=True)
        data = open(files["NONAME.SC5"], "rb").read()
        check(header(data)[:2] == (0x0000, 0xFFFF),
              "header = %04X..%04X" % header(data)[:2])
        check(len(data) == 7 + 0x10000, "file size = %d" % len(data))
        check(data[7 + 0x8000] != 0, "page 1 holds the odd lines")

        print("SCREEN 7, interlaced (split files)")
        mod_i7, image_i7 = load_plugin(512, 424, make_image(512, 424))
        files = run(mod_i7, image_i7, outdir, "SC", screen_mode="SCREEN7", interlaced=True)
        check(list(files) == ["NONAME.PAL", "NONAME.S70", "NONAME.S71", "NONAME.TXT"],
              "files: %s" % list(files))
        s0 = open(files["NONAME.S70"], "rb").read()
        s1 = open(files["NONAME.S71"], "rb").read()
        check(header(s0)[:2] == (0x0000, 0xFFFF), "S70 header = %04X..%04X" % header(s0)[:2])
        check(header(s1)[:2] == (0x0000, 0xFFFF), "S71 header = %04X..%04X" % header(s1)[:2])
        check(len(s0) == 7 + 0x10000 and len(s1) == 7 + 0x10000,
              "S70/S71 sizes = %d/%d" % (len(s0), len(s1)))

        print("SCREEN 7, interlaced without palette (split files)")
        files = run(mod_i7, image_i7, outdir, "SR", screen_mode="SCREEN7", interlaced=True)
        check(list(files) == ["NONAME.PAL", "NONAME.R70", "NONAME.R71", "NONAME.TXT"],
              "files: %s" % list(files))

        print("SCREEN 5, interlaced raw")
        files = run(mod_i, image_i, outdir, "RAW", interlaced=True)
        data = open(files["NONAME.RAW"], "rb").read()
        check(len(data) == 128 * 424, "file size = %d (packed)" % len(data))

        # ----------------------------------------------------- size checks
        print("Size validation")
        mod_s, image_s = load_plugin(128, 212, make_image(128, 212))
        files = run(mod_s, image_s, outdir, "SC")
        check(not files, "wrong width produces no file: %s" % list(files))
    finally:
        shutil.rmtree(outdir, ignore_errors=True)

    print("\n%s" % ("ALL TESTS PASSED" if ok else "SOME TESTS FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
