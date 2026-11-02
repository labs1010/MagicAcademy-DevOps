from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import Course, Enrollment
from tests.helpers import admin, headers, register

pytestmark = pytest.mark.integration


def test_postgresql_persistence_and_constraints(pg_app):
    with TestClient(pg_app) as client:
        register(client, "student")
        auth = headers(client, "student")
        course = client.post(
            "/admin/courses",
            headers=admin(pg_app, client),
            json={"title": "PostgreSQL", "capacity": 2},
        ).json()
        response = client.post(f"/courses/{course['id']}/enroll", headers=auth)
        assert response.status_code == 201
        item = response.json()
        with pg_app.state.session_factory() as db:
            assert db.get(Enrollment, item["id"]).user_id == item["user_id"]
            db.add(Enrollment(user_id=item["user_id"], course_id=course["id"]))
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
            db.add(Course(title="Invalid", capacity=0))
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()


@pytest.mark.concurrency
@pytest.mark.parametrize("same_user", [False, True])
def test_concurrent_enrollment(pg_app, same_user):
    count, capacity = 20, 5
    with TestClient(pg_app) as setup:
        tokens = []
        for i in range(count if not same_user else 1):
            register(setup, f"student_{i}")
            tokens.append(headers(setup, f"student_{i}"))
        if same_user:
            tokens *= count
        course = setup.post(
            "/admin/courses",
            headers=admin(pg_app, setup),
            json={"title": "Popular", "capacity": capacity},
        ).json()
        barrier = Barrier(count)

        def enroll(token):
            # Independent HTTP clients share only the app and its connection pool.
            client = TestClient(pg_app, raise_server_exceptions=False)
            try:
                barrier.wait(timeout=20)
                return client.post(f"/courses/{course['id']}/enroll", headers=token).status_code
            finally:
                client.close()

        with ThreadPoolExecutor(max_workers=count) as pool:
            codes = list(pool.map(enroll, tokens))
        expected = 1 if same_user else capacity
        assert codes.count(201) == expected
        assert codes.count(409) == count - expected
        with pg_app.state.session_factory() as db:
            assert db.scalar(select(func.count()).select_from(Enrollment)) == expected
