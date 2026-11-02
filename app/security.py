from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
# Avoid returning faster when a username does not exist.
DUMMY_HASH = hasher.hash("unused-password-for-constant-work")


def hash_password(password):
    return hasher.hash(password)


def verify_password(password, encoded):
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def create_token(user_id, settings):
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=settings.token_minutes)},
        settings.jwt_secret,
        algorithm="HS256",
    )


def decode_token(token, settings):
    return jwt.decode(
        token, settings.jwt_secret, algorithms=["HS256"], options={"require": ["sub", "exp", "iat"]}
    )
