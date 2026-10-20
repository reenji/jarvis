"""Cross-platform one-time ARGUS setup (Windows, macOS, Linux)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"
PYTHON = VENV / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")


def run(*args: str) -> None:
    print("+", " ".join(args))
    subprocess.check_call(args, cwd=ROOT)


def main() -> int:
    print("ARGUS setup — Windows / macOS / Linux")
    if sys.version_info < (3, 11):
        print(
            "Python 3.11+ is required. "
            "Run this script with a supported Python interpreter: "
            "https://www.python.org/downloads/"
        )
        return 1
    # Reuse the interpreter that launched this script. On Windows, `python3`
    # may resolve to the Microsoft Store app-execution alias even when Python
    # is already installed and this script is running successfully.
    host_python = sys.executable

    if not PYTHON.exists():
        run(host_python, "-m", "venv", str(VENV))
    run(str(PYTHON), "-m", "pip", "install", "--upgrade", "pip")
    run(str(PYTHON), "-m", "pip", "install", "-r", "requirements.txt")
    run(str(PYTHON), "-m", "pip", "install", "-e", ".")

    env_file = ROOT / ".env"
    if not env_file.exists():
        shutil.copyfile(ROOT / ".env.example", env_file)
        print("Created .env. Add your GEMINI_API_KEY before launching.")
    else:
        print("Keeping existing .env.")

    command_dir = VENV / ("Scripts" if os.name == "nt" else "bin")
    print("\nSetup complete.")
    print(f"Activate the environment: {command_dir / ('activate.bat' if os.name == 'nt' else 'activate')}")
    print("Then launch with: argus")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
