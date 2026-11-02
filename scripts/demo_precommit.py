"""Demonstrate commit rejection in a TEMPORARY repository, never dirty the project."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        env = os.environ.copy()
        env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env["PATH"]

        def run(*args, check=True):
            return subprocess.run(
                args, cwd=path, env=env, capture_output=True, text=True, check=check
            )

        run("git", "init", "-b", "main")
        run("git", "config", "user.name", "Local Hook Demo")
        run("git", "config", "user.email", "demo@example.invalid")
        for name in [".pre-commit-config.yaml", "pyproject.toml"]:
            shutil.copy(ROOT / name, path / name)
        run(sys.executable, "-m", "pre_commit", "install")
        evidence = []
        for label, code in [("style", "import os\n"), ("syntax", "def broken(\n")]:
            (path / "example.py").write_text(code)
            run("git", "add", ".")
            result = run("git", "commit", "-m", label, check=False)
            assert result.returncode != 0, "A bad commit was accepted!"
            evidence.append(
                f"{label}: rejected (exit {result.returncode})\n{result.stdout}{result.stderr}"
            )
        (path / "example.py").write_text('print("Valid code")\n')
        run("git", "add", ".")
        result = run("git", "commit", "-m", "Valid code")
        evidence.append("valid: accepted\n" + result.stdout + result.stderr)
        target = ROOT / "results/precommit_demo.txt"
        target.write_text("\n".join(evidence), encoding="utf-8")
        print(target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
