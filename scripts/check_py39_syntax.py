#!/usr/bin/env python
"""Fail if any package source file uses syntax newer than Python 3.9.

Slicer's bundled Python is typically 3.9; keep vatquant_core importable there.
"""

from __future__ import annotations

import ast
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TARGETS = [
    os.path.join(ROOT, "vatquant_core"),
    os.path.join(ROOT, "scripts"),
    os.path.join(ROOT, "tests"),
]


def check_file(path: str) -> None:
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    try:
        ast.parse(source, filename=path, feature_version=(3, 9))
    except TypeError:
        # Older Python without feature_version: just parse normally
        ast.parse(source, filename=path)
    except SyntaxError as exc:
        raise SystemExit("Python 3.9 syntax check failed for {}: {}".format(path, exc))


def main() -> int:
    count = 0
    for base in TARGETS:
        if not os.path.isdir(base):
            continue
        for root, _dirs, files in os.walk(base):
            for name in files:
                if name.endswith(".py"):
                    check_file(os.path.join(root, name))
                    count += 1
    print("OK: {} files parse as Python 3.9-compatible AST".format(count))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
