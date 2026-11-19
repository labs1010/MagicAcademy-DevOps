"""Build, verify DB/API and data survival in a disposable isolated Compose project."""

import argparse
import json
import os
import secrets
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def wait_ready(client):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            if client.get("/health").status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise RuntimeError("API did not become healthy")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()
    os.chdir(ROOT)
    project = "magic-check-" + secrets.token_hex(4)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    evidence = {"project": project, "checks": []}
    with tempfile.TemporaryDirectory() as directory:
        env_file = Path(directory) / ".env"
        env_file.write_text(
            f"APP_ENV=sandbox\nPOSTGRES_USER=academy\nPOSTGRES_PASSWORD={secrets.token_hex(24)}\n"
            f"POSTGRES_DB=magic_sandbox\nJWT_SECRET={secrets.token_hex(32)}\nAPI_PORT={port}\n"
        )
        base = [
            "docker",
            "compose",
            "--env-file",
            str(env_file),
            "-p",
            project,
            "-f",
            str(ROOT / "docker-compose.yml"),
        ]
        env = os.environ.copy()
        for key in [
            "APP_ENV",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_DB",
            "JWT_SECRET",
            "API_PORT",
        ]:
            env.pop(key, None)

        env["PLANNER_PORT"] = "0"

        def compose(*args):
            return subprocess.run(
                [*base, *args], env=env, text=True, capture_output=True, check=True
            )

        try:
            compose("config", "--quiet")
            evidence["checks"].append("compose config passed")
            compose(
                "up",
                "--no-build" if args.no_build else "--build",
                "-d",
                "--wait",
                "--wait-timeout",
                "180",
            )
            evidence["checks"].append("build and healthchecks passed")
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=10) as client:
                wait_ready(client)
                account = {"username": "persist_student", "password": secrets.token_urlsafe(20)}
                created = client.post("/auth/register", json=account)
                created.raise_for_status()
                user_id = created.json()["id"]
                evidence["checks"].append("registration through API passed")
                query = compose(
                    "exec",
                    "-T",
                    "db",
                    "psql",
                    "-U",
                    "academy",
                    "-d",
                    "magic_sandbox",
                    "-tAc",
                    "SELECT count(*) FROM users WHERE username='persist_student'",
                )
                assert query.stdout.strip() == "1"
                evidence["checks"].append("SQL query verified persisted user")
                compose("down")  # Named volume deliberately survives this operation.
                compose("up", "-d", "--wait", "--wait-timeout", "180")
                wait_ready(client)
                login = client.post("/auth/token", data=account)
                login.raise_for_status()
                profile = client.get(
                    "/users/me", headers={"Authorization": "Bearer " + login.json()["access_token"]}
                )
                assert profile.json()["id"] == user_id
                evidence["checks"].append("same user survived container removal and recreation")
            evidence["status"] = "passed"
        except Exception as exc:
            evidence["status"] = "failed"
            evidence["error"] = str(exc)
            raise
        finally:
            (ROOT / "results").mkdir(exist_ok=True)
            (ROOT / "results/docker_verification.json").write_text(json.dumps(evidence, indent=2))
            # Remove ONLY this script's disposable project and volume, never the main project.
            try:
                compose("down", "-v")
            except (OSError, subprocess.SubprocessError):
                pass


if __name__ == "__main__":
    main()
