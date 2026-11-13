#!/usr/bin/env python3
"""Optional cross-check of the exported files against a real V9938.

Runs a headless openMSX instance (MSX2 with 128kB of VRAM), switches the VDP
to the wanted screen mode, writes a file produced by the plug-in into the
emulated VRAM and dumps the emulated screen back.

This is a *diagnostic* tool, not a pass/fail test: openMSX's `vpoke`/`vpeek`
Tcl commands do not give the programmer's view of the VRAM in GRAPHIC 6/7
mode (the physical VRAM is interleaved by even/odd bytes between the chips),
so the dump may show the bytes of a pair swapped. The script reports which
of the two interpretations matches, which is what tells us whether the
bitmap layout is linear.

Requirements: openMSX in $PATH and a working display. It takes a few minutes
(every byte is transferred through the emulator's control protocol).

Usage:  python3 tests/verify_with_openmsx.py
"""
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from omsx import OpenMSX, GRAPHIC4, GRAPHIC6     # noqa: E402
import test_g4 as t3                            # noqa: E402

LINES = 32          # number of bitmap lines transferred (each vpoke is a round trip)
MACHINE = "Yamaha_CX5MII-128"


def export(outdir, encoding, screen_mode, interlaced, width, height):
    mod = t3.load_plugin()
    files = t3.run(mod, outdir, encoding, screen_mode=screen_mode,
                   interlaced=interlaced, width=width, height=height, dithering=0)
    return files


def write_bytes(omsx, data, base=0):
    """Write the bytes so that a pair of VRAM bytes always gets the same value.

    The VRAM is written in decreasing order and the odd byte of a pair is
    written first: that way the (possibly) spilling write cannot destroy the
    neighbour that was written before.
    """
    for i in range(len(data) - 1, -1, -1):
        omsx.vpoke(base + i, data[i])


def compare(dump, data, count):
    """Compare two byte sequences.

    openMSX's VRAM debug commands work on the physical VRAM, where the bytes
    of a pair share a single value (the chips are interleaved by even/odd
    address). Three interpretations are therefore accepted:
      * the bytes are identical;
      * the bytes of each pair are duplicated (the even byte is repeated);
      * the bytes of each pair are swapped.
    """
    if all(dump[i] == data[i] for i in range(count)):
        return "identical"
    if all(dump[2 * k] == data[2 * k] and dump[2 * k + 1] == data[2 * k]
           for k in range(count // 2)):
        return "identical, the bytes of each pair share one value"
    if all(dump[i] == data[i ^ 1] for i in range(count)):
        return "identical with the bytes of each pair swapped"
    for i in range(count):
        if dump[i] != data[i]:
            return "different at byte %d (dump %02X, file %02X)" % (i, dump[i], data[i])
    return "different"


def check_sc7(outdir):
    """SCREEN 7: the bitmap must show up on the emulated screen unchanged."""
    print("SCREEN 7 (GRAPHIC 6): linear bitmap check")
    files = export(outdir, "SC", "SCREEN7", False, 512, 212)
    bitmap = open(files["NONAME.SC7"], "rb").read()[7:]     # skip the BSAVE header
    omsx = OpenMSX(machine=MACHINE)
    try:
        omsx.send("set power on")
        time.sleep(12)                       # let the machine boot
        for n, v in GRAPHIC6.items():
            omsx.vdpreg(n, v)
        time.sleep(2)
        write_bytes(omsx, bitmap[:LINES * 256])
        base = os.path.join(outdir, "sc7dump")
        omsx.save_screen(base)
    finally:
        omsx.close()
    dump = open(base + ".SC7", "rb").read()[7:]
    print("  screen dump vs exported bitmap:", compare(dump, bitmap, LINES * 256))


def check_interlaced(outdir):
    """SCREEN 5 interlaced: page 0 holds the even lines, page 1 the odd ones."""
    print("SCREEN 5 interlaced: even/odd page check")
    files = export(outdir, "SR", "SCREEN5", True, 256, 424)
    data = open(files["NONAME.SR5"], "rb").read()[7:]       # skip the BSAVE header
    even = data[:128 * 212]                  # page 0: the even lines
    odd = data[0x8000:0x8000 + 128 * 212]     # page 1: the odd lines
    omsx = OpenMSX(machine=MACHINE)
    try:
        omsx.send("set power on")
        time.sleep(12)
        regs = dict(GRAPHIC4)
        regs[9] = 0x80 | 0x0C          # LN + interlace (IL) + even/odd (EO)
        regs[2] = 0x1F | 0x10          # odd page address in R#2
        for n, v in regs.items():
            omsx.vdpreg(n, v)
        time.sleep(2)
        print("  screen mode: %s, R#2 = %s, R#9 = %s"
              % (omsx.send("get_screen_mode"), omsx.send("vdpreg 2"), omsx.send("vdpreg 9")))
        write_bytes(omsx, even[:LINES * 128])
        write_bytes(omsx, odd[:LINES * 128], base=0x8000)
        base = os.path.join(outdir, "il5dump")
        omsx.save_screen(base)
    finally:
        omsx.close()
    # in interlaced mode openMSX dumps both pages: the ".SC5" file holds the
    # odd page (R#2 selects the odd page) and the ".S1" file the even one.
    # The mode number is appended to the extension by openMSX (".S15").
    # Only the odd page can be compared byte for byte: the writes that filled
    # the even page were overwritten by the ones of the odd page.
    page_odd = open(base + ".SC5", "rb").read()[7:]
    print("  odd page  vs export:", compare(page_odd, odd, LINES * 128))
    if not os.path.exists(base + ".S15"):
        print("  even page: openMSX did not dump the second page (not in interlaced mode?)")
        return
    page_even = open(base + ".S15", "rb").read()[7:]
    print("  even page vs export:", compare(page_even, even, LINES * 128))


def main():
    outdir = tempfile.mkdtemp(prefix="msx-g4-emu-")
    try:
        check_sc7(outdir)
        check_interlaced(outdir)
    finally:
        shutil.rmtree(outdir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
