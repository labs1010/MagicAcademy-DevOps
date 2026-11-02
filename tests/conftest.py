import os
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import create_app


@pytest.fixture
def settings():
    return SimpleNamespace(
        app_env="sandbox", database_url="unused", jwt_secret="t" * 48, token_minutes=60, debug=True
    )


@pytest.fixture
def app(settings, monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if url:
        parsed = make_url(url)
        if parsed.drivername != "postgresql+psycopg" or parsed.database != "magic_test":
            pytest.fail("Tests may only reset PostgreSQL magic_test")
        engine = create_engine(url, pool_pre_ping=True)
    else:
        # HTTP/ORM integration substitute, NOT PostgreSQL or concurrency validation.
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.drop_all(engine)
    monkeypatch.setattr("app.main.make_database", lambda _: (engine, sessions))
    app = create_app(settings)
    yield app
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def pg_app(settings):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL missing: PostgreSQL checks not executed")
    parsed = make_url(url)
    if parsed.drivername != "postgresql+psycopg" or parsed.database != "magic_test":
        pytest.fail("Destructive tests require a dedicated PostgreSQL database magic_test")
    settings.database_url = url
    app = create_app(settings)
    # Never touch sandbox/production. No parallel pytest workers are supported.
    Base.metadata.drop_all(app.state.engine)
    Base.metadata.create_all(app.state.engine)
    with app.state.engine.connect() as db:
        assert db.scalar(text("SELECT current_database()")) == "magic_test"
    yield app
    Base.metadata.drop_all(app.state.engine)
    app.state.engine.dispose()
