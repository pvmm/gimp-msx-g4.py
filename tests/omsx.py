#!/usr/bin/env python3
"""Minimal openMSX control-protocol client (stdio XML).

Used by verify_with_openmsx.py to drive a headless openMSX instance:
the machine is booted, VDP registers are poked, VRAM is filled and the
emulated screen is dumped to a file.

openMSX is launched with:
    openmsx -control stdio -machine <machine> -command 'set renderer none'

The protocol: send "<openmsx-control>" once, then
"<command>...</command>" / "<reply result="ok|nok">...</reply>" exchanges.
"""
import html
import re
import subprocess
import time

OPENMSX = "openmsx"


class OpenMSX:
    def __init__(self, machine="Yamaha_CX5MII-128", renderer="none"):
        args = [OPENMSX, "-control", "stdio", "-machine", machine]
        if renderer:
            args += ["-command", "set renderer %s" % renderer]
        self.p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, bufsize=1)
        self.buf = ""
        self._wait_for("<openmsx-output>")
        self.p.stdin.write("<openmsx-control>\n")
        self.p.stdin.flush()

    def _wait_for(self, marker, timeout=60):
        deadline = time.time() + timeout
        while marker not in self.buf:
            if time.time() > deadline:
                raise TimeoutError("timeout waiting for %s (buffer=%r)"
                                   % (marker, self.buf[-400:]))
            chunk = self.p.stdout.readline()
            if not chunk:
                raise RuntimeError("openMSX died: %s" % self.p.stderr.read()[-2000:])
            self.buf += chunk
        idx = self.buf.index(marker) + len(marker)
        out, self.buf = self.buf[:idx], self.buf[idx:]
        return out

    def send(self, cmd, timeout=60):
        """Run a Tcl command and return its output."""
        self.p.stdin.write("<command>%s</command>\n" % html.escape(cmd))
        self.p.stdin.flush()
        out = self._wait_for("</reply>", timeout)
        m = re.search(r'<reply result="(ok|nok)"[^>]*>(.*?)</reply>', out, re.S)
        if not m:
            return out.strip()
        content = html.unescape(m.group(2).strip())
        return content if m.group(1) == "ok" else "ERROR: " + content

    # convenience wrappers -------------------------------------------------
    def vpoke(self, addr, value):
        return self.send("vpoke 0x%05X 0x%02X" % (addr, value))

    def vpeek(self, addr):
        return self.send("vpeek 0x%05X" % addr)

    def vdpreg(self, reg, value):
        return self.send("vdpreg %d 0x%02X" % (reg, value))

    def save_screen(self, basename):
        return self.send('save_msx_screen "%s"' % basename)

    def close(self):
        try:
            self.p.stdin.write("<command>exit</command>\n")
            self.p.stdin.flush()
        except Exception:
            pass
        try:
            self.p.wait(timeout=5)
        except Exception:
            self.p.kill()


# V9938 register settings ---------------------------------------------------
# GRAPHIC 4 (SCREEN 5): 256x212, 16 colors, 32K page, palette at 0x7680
GRAPHIC4 = {0: 0x06, 1: 0x40, 2: 0x1F, 3: 0x76, 4: 0x3F, 5: 0x76, 6: 0x3F,
            7: 0x00, 8: 0x10, 9: 0x80, 10: 0x00, 13: 0x00}
# GRAPHIC 6 (SCREEN 7): 512x212, 16 colors, 64K page, palette at 0xFA80
GRAPHIC6 = {0: 0x0A, 1: 0x40, 2: 0x1F, 3: 0xFA, 4: 0x3F, 5: 0xFA, 6: 0x3F,
            7: 0x00, 8: 0x10, 9: 0x80, 10: 0x00, 13: 0x00}
