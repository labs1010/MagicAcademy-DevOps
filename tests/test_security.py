from datetime import UTC, datetime, timedelta

import jwt
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.security import create_token, decode_token, hash_password, verify_password


def test_hash_is_salted_and_verified():
    a, b = hash_password("long password"), hash_password("long password")
    assert a != b and "long password" not in a
    assert verify_password("long password", a)
    assert not verify_password("wrong password", a)
    assert not verify_password("anything", "broken hash")


def test_token_roundtrip_and_tampering(settings):
    token = create_token(7, settings)
    assert decode_token(token, settings)["sub"] == "7"
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token + "x", settings)


def test_expired_token(settings):
    old = datetime.now(UTC) - timedelta(hours=2)
    token = jwt.encode({"sub": "7", "iat": old, "exp": old}, settings.jwt_secret, algorithm="HS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token, settings)


@pytest.mark.parametrize(
    "environment,dbname", [("sandbox", "magic_sandbox"), ("production", "magic_production")]
)
def test_environment_config(environment, dbname):
    config = Settings(
        app_env=environment,
        database_url=f"postgresql+psycopg://u:p@db/{dbname}",
        jwt_secret="s" * 48,
    )
    assert config.debug is (environment == "sandbox")


def test_production_rejects_sandbox_database():
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://u:p@db/magic_sandbox",
            jwt_secret="s" * 48,
        )


def test_placeholder_secret_rejected():
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql+psycopg://u:p@db/magic_sandbox",
            jwt_secret="CHANGE_" + "x" * 40,
        )
