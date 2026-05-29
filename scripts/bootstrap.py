#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"


def venv_python() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def run(args: list[str]) -> None:
    subprocess.check_call(args, cwd=ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a venv and install Background Remover dependencies.")
    parser.add_argument("--upgrade", action="store_true", help="Upgrade installed packages inside the venv.")
    parser.add_argument("--warm-model", action="store_true", help="Import rembg and create the default model session after install.")
    args = parser.parse_args()

    if sys.version_info < (3, 10):
        raise SystemExit("Python 3.10 or newer is required.")

    if not VENV.exists():
        venv.EnvBuilder(with_pip=True).create(VENV)

    py = str(venv_python())
    run([py, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
    install_args = [py, "-m", "pip", "install", "-e", "."]
    if args.upgrade:
        install_args.insert(4, "--upgrade")
    run(install_args)

    if args.warm_model:
        run([py, "-c", "from rembg import new_session; new_session('u2net'); print('u2net model ready')"])

    print("Installed. Activate the venv, then run: background-remover")


if __name__ == "__main__":
    main()
