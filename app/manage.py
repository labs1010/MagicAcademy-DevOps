"""Run inside API container: python -m app.manage USERNAME (password prompt)."""

import argparse
from getpass import getpass

from sqlalchemy import select

from app.config import load_settings
from app.database import Base, make_database
from app.models import User
from app.schemas import Registration
from app.security import hash_password


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("username")
    args = parser.parse_args()
    password = getpass("New administrator password (10+ characters): ")
    if password != getpass("Repeat password: "):
        raise SystemExit("Passwords differ")
    data = Registration(username=args.username, password=password)
    engine, sessions = make_database(load_settings().database_url)
    Base.metadata.create_all(engine)
    with sessions() as db:
        if db.scalar(select(User.id).where(User.username == data.username)):
            raise SystemExit("User exists; no account was changed")
        db.add(User(username=data.username, password_hash=hash_password(password), role="ADMIN"))
        db.commit()
    engine.dispose()
    print("Administrator created")


if __name__ == "__main__":
    main()
