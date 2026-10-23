"""Build and smoke-test the installable CLI wheel in an isolated environment."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="argus-wheel-check-") as temporary:
        scratch = Path(temporary)
        wheelhouse = scratch / "wheelhouse"
        wheelhouse.mkdir()
        build = run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--disable-pip-version-check",
                "--wheel-dir",
                str(wheelhouse),
                ".",
            ],
            cwd=ROOT,
        )
        if build.returncode:
            sys.stderr.write(build.stdout + build.stderr)
            return build.returncode

        wheels = list(wheelhouse.glob("*.whl"))
        if len(wheels) != 1:
            print(f"Expected one wheel, found {len(wheels)}.", file=sys.stderr)
            return 1

        environment = scratch / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        windows = platform.system() == "Windows"
        scripts = environment / ("Scripts" if windows else "bin")
        python = scripts / ("python.exe" if windows else "python")
        argus = scripts / ("argus.exe" if windows else "argus")

        install = run(
            [str(python), "-m", "pip", "install", "--disable-pip-version-check", str(wheels[0])],
            cwd=ROOT,
        )
        if install.returncode:
            sys.stderr.write(install.stdout + install.stderr)
            return install.returncode

        version = run([str(argus), "--version"], cwd=ROOT)
        if version.returncode:
            sys.stderr.write(version.stdout + version.stderr)
            return version.returncode
        print(version.stdout.strip())

        doctor_home = scratch / "doctor-home"
        doctor_env = os.environ.copy()
        for name in (
            "ARGUS_CONFIG_FILE",
            "ARGUS_LLM_GEMINI_API_KEY",
            "ARGUS_SESSION_DB",
            "GEMINI_API_KEY",
        ):
            doctor_env.pop(name, None)
        doctor_env["ARGUS_HOME"] = str(doctor_home)
        doctor = run([str(argus), "doctor"], cwd=scratch, env=doctor_env)
        if doctor.returncode != 1:
            sys.stderr.write(doctor.stdout + doctor.stderr)
            print(
                "Expected doctor to report the missing API key with exit 1; "
                f"got {doctor.returncode}.",
                file=sys.stderr,
            )
            return 1
        if "No usable API key found" not in doctor.stdout:
            sys.stderr.write(doctor.stdout + doctor.stderr)
            print("Doctor did not report the expected missing-key hint.", file=sys.stderr)
            return 1
        if "SQLite storage" not in doctor.stdout:
            sys.stderr.write(doctor.stdout + doctor.stderr)
            print("Doctor did not complete its local storage check.", file=sys.stderr)
            return 1
        print("Clean wheel install and doctor smoke check passed without a Gemini request.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
