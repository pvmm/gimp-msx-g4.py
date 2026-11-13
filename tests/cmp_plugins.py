#!/usr/bin/env python3
"""Both plug-ins must produce exactly the same files.

The GIMP 2 and the GIMP 3 versions of the plug-in are kept in sync by hand,
so every encoding/screen mode combination is exported with both and the
results are compared byte for byte.

Usage:  python3 tests/cmp_plugins.py
"""
import hashlib
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import test_g4 as t3          # noqa: E402
import test_g4_gimp2 as t2    # noqa: E402

CASES = [
    # encoding, screen mode, interlaced, width, height
    ("SC",  "SCREEN5", False, 256, 212),
    ("SR",  "SCREEN5", False, 256, 212),
    ("SC",  "SCREEN7", False, 512, 212),
    ("SR",  "SCREEN7", False, 512, 212),
    ("SC",  "SCREEN5", True,  256, 424),
    ("SR",  "SCREEN5", True,  256, 424),
    ("SC",  "SCREEN7", True,  512, 424),
    ("RAW", "SCREEN5", False, 256, 212),
    ("RAW", "SCREEN5", True,  256, 424),
    ("DAT", "SCREEN5", False, 256, 212),
]


def digest(paths):
    return {os.path.basename(p): hashlib.sha256(open(p, "rb").read()).hexdigest()
            for p in paths.values()}


def main():
    ok = True
    mod3 = t3.load_plugin()
    out3 = tempfile.mkdtemp(prefix="msx-g4-cmp3-")
    out2 = tempfile.mkdtemp(prefix="msx-g4-cmp2-")
    try:
        for (enc, mode, interl, w, h) in CASES:
            for d in (out3, out2):
                for f in os.listdir(d):
                    os.remove(os.path.join(d, f))
            files3 = t3.run(mod3, out3, enc, screen_mode=mode, interlaced=interl,
                            width=w, height=h, dithering=0)
            mod2, image2 = t2.load_plugin(w, h, t2.make_image(w, h))
            files2 = t2.run(mod2, image2, out2, enc, screen_mode=mode, interlaced=interl)
            same = digest(files3) == digest(files2)
            ok = ok and same
            print("%-4s %-8s interlaced=%-5s %dx%d -> %s"
                  % (enc, mode, interl, w, h, "SAME" if same else "DIFFERENT"))
            if not same:
                print("   gimp3: %s" % digest(files3))
                print("   gimp2: %s" % digest(files2))
    finally:
        shutil.rmtree(out3, ignore_errors=True)
        shutil.rmtree(out2, ignore_errors=True)
    print("\n%s" % ("ALL IDENTICAL" if ok else "MISMATCH"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
