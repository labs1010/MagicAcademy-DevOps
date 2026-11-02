"""Run all tests against the dedicated magic_test database in the dev stack."""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    os.chdir(ROOT)
    values = dotenv_values(".env")
    if values.get("APP_ENV") != "sandbox":
        raise SystemExit("Tests require the sandbox .env file")
    base = ["docker", "compose", "-f", "docker-compose.yml", "-f", "compose.dev.yml"]
    subprocess.run([*base, "up", "--build", "-d", "--wait"], check=True)
    user = values["POSTGRES_USER"]
    exists = subprocess.check_output(
        [
            *base,
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            user,
            "-d",
            values["POSTGRES_DB"],
            "-tAc",
            "SELECT 1 FROM pg_database WHERE datname='magic_test'",
        ],
        text=True,
    ).strip()
    if exists != "1":
        subprocess.run(
            [*base, "exec", "-T", "db", "createdb", "-U", user, "magic_test"], check=True
        )
    env = os.environ.copy()
    env["TEST_DATABASE_URL"] = (
        f"postgresql+psycopg://{user}:{values['POSTGRES_PASSWORD']}@localhost:5433/magic_test"
    )
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--junitxml=results/pytest_postgres.xml"], env=env
    )
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
