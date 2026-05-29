#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import platform
import sys

REQUIRED = ["flask", "PIL", "rembg", "onnxruntime"]


def main() -> int:
    print(f"Python: {sys.version.split()[0]}")
    print(f"Platform: {platform.platform()}")
    print(f"Machine: {platform.machine()}")

    if sys.version_info < (3, 10):
        print("FAIL: Python 3.10 or newer is required.")
        return 1

    missing = []
    for module in REQUIRED:
        if importlib.util.find_spec(module) is None:
            missing.append(module)
            print(f"FAIL: missing {module}")
        else:
            print(f"OK: {module}")

    if missing:
        print("Install dependencies with: python scripts/bootstrap.py")
        return 1

    print("Preflight passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
