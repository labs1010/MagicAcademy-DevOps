"""Generate local secrets with Python standard library, before docker compose up."""

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    for environment, port in [("sandbox", 8000), ("production", 8001)]:
        path = ROOT / f".env.{environment}"
        if path.exists():
            print(f"Keeping {path.name}")
            continue
        password = secrets.token_hex(24)
        path.write_text(
            f"APP_ENV={environment}\nPOSTGRES_USER=academy\n"
            f"POSTGRES_PASSWORD={password}\nPOSTGRES_DB=magic_{environment}\n"
            f"JWT_SECRET={secrets.token_hex(32)}\nAPI_PORT={port}\n"
            f"DATABASE_URL=postgresql+psycopg://academy:{password}@localhost:5433/magic_{environment}\n",
            encoding="utf-8",
        )
        print(f"Created {path.name}")
    target = ROOT / ".env"
    if not target.exists():
        target.write_bytes((ROOT / ".env.sandbox").read_bytes())
        print("Created .env for Compose sandbox")


if __name__ == "__main__":
    main()
