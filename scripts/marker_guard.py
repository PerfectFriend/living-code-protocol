#!/usr/bin/env python3
"""Single source of truth for "is it safe to stamp '# HOT'/'# COLD' here?".

The Lord's mtime walkers mark hot/cold code by writing a marker line at line 1.
That is only valid where '#' is a real comment AND line 1 may be replaced.
Proven damage (elemental-life-2, 2026-09-28 and again 2026-09-29):
  * lib/*.dart, test/*.dart  -> `flutter test` died: "Type 'HOT' not found"
  * *.xml (before <?xml ...?>) -> invalid XML
  * android/gradlew           -> shebang destroyed (line 1 must start with '#!')
  * linux/runner/*.cc/.h, *.kt/.java -> C/C++ read it as a preprocessor directive
  * *.svg                     -> invalid SVG (asset will not render)
  * pubspec.lock / *.csv      -> digest/CSV header corrupted
  * *.png                     -> binary overwritten with text (asset lost)

Rule: allow-list of formats where '#' is a comment; never touch binaries; never
precede a shebang or an XML declaration; never write non-UTF-8.

Both walkers import this module:
  orchestration/scripts/lord_of_code.py  (the one the hourly Lord cron runs)
  /home/thomas/LivingCode/update_all_markers.py
"""
import os

SAFE_SUFFIXES = (
    '.md', '.rst', '.txt',
)
SHEBANG_EXCEPTIONS = ('gradlew', 'gradlew.bat', 'configure')


def marker_safe(filepath):
    """True only when a leading '# HOT'/'# COLD' line cannot break the file."""
    name = os.path.basename(filepath)
    if name in SHEBANG_EXCEPTIONS:
        return False
    if not name.endswith(SAFE_SUFFIXES):
        return False
    try:
        with open(filepath, 'rb') as f:
            head = f.read(8192)
    except Exception:
        return False
    if b'\x00' in head:                      # binary (png/pdf/zip/...)
        return False
    if head.startswith(b'#!'):               # shebang must stay on line 1
        return False
    if head.lstrip().startswith(b'<?xml'):   # XML declaration must stay first
        return False
    try:
        head.decode('utf-8')
    except UnicodeDecodeError:
        return False
    return True
