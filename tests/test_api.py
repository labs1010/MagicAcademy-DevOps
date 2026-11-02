import pytest
from sqlalchemy import select

from app.models import User
from tests.helpers import PASSWORD, admin, headers, register


@pytest.mark.parametrize("path", ["/users/me", "/user/home", "/admin/home", "/enrollments/me"])
def test_anonymous_denied(client, path):
    assert client.get(path).status_code == 401


def test_registration_and_login(client, app):
    user = register(client, "student")
    assert user["role"] == "USER" and "password_hash" not in user
    with app.state.session_factory() as db:
        stored = db.scalar(select(User).where(User.username == "student"))
        assert stored.password_hash.startswith("$argon2id$")
    assert client.get("/user/home", headers=headers(client, "student")).status_code == 200
    assert (
        client.post("/auth/token", data={"username": "student", "password": "wrong"}).status_code
        == 401
    )
    assert (
        client.post("/auth/token", data={"username": "missing", "password": PASSWORD}).status_code
        == 401
    )
    assert (
        client.post(
            "/auth/register", json={"username": "student", "password": PASSWORD}
        ).status_code
        == 409
    )


def test_privilege_escalation_rejected(client):
    response = client.post(
        "/auth/register", json={"username": "intruder", "password": PASSWORD, "role": "ADMIN"}
    )
    assert response.status_code == 422


def test_roles(client, app):
    register(client, "student")
    token = headers(client, "student")
    assert client.get("/admin/home", headers=token).status_code == 403
    assert (
        client.post(
            "/admin/courses", headers=token, json={"title": "Fire", "capacity": 2}
        ).status_code
        == 403
    )
    assert client.get("/admin/home", headers=admin(app, client)).status_code == 200


def test_idor_profile(client):
    alice, bob = register(client, "alice"), register(client, "bob")
    token = headers(client, "alice")
    assert (
        client.patch(
            f"/users/{bob['id']}", headers=token, json={"display_name": "Changed"}
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/users/{alice['id']}", headers=token, json={"display_name": "Alice"}
        ).status_code
        == 200
    )
    assert client.get("/users/me", headers=headers(client, "bob")).json()["display_name"] == ""
    assert (
        client.patch(
            f"/users/{alice['id']}", headers=token, json={"display_name": "Alice", "role": "ADMIN"}
        ).status_code
        == 422
    )


def test_enrollment_capacity_duplicate_and_idor(client, app):
    register(client, "alice")
    register(client, "bob")
    a, b = headers(client, "alice"), headers(client, "bob")
    course = client.post(
        "/admin/courses", headers=admin(app, client), json={"title": "Teleportation", "capacity": 1}
    ).json()
    path = f"/courses/{course['id']}/enroll"
    assert client.post(path).status_code == 401
    created = client.post(path, headers=a)
    assert created.status_code == 201
    assert client.post(path, headers=a).json()["detail"] == "Already enrolled"
    assert client.post(path, headers=b).json()["detail"] == "Course is full"
    assert client.get("/courses").json()[0]["available_seats"] == 0
    entity = f"/enrollments/{created.json()['id']}"
    assert client.get(entity, headers=b).status_code == 403
    assert client.get(entity, headers=a).status_code == 200
    assert len(client.get("/enrollments/me", headers=a).json()) == 1
    assert client.get("/enrollments/me", headers=b).json() == []
    assert client.post("/courses/999/enroll", headers=a).status_code == 404


def test_invalid_token_and_payload(client):
    assert client.get("/users/me", headers={"Authorization": "Bearer bad"}).status_code == 401
    assert client.post("/auth/register", json={"username": "a", "password": "x"}).status_code == 422


def test_error_response_hides_internals(client, app):
    @app.get("/test-only-error")
    def broken():
        raise RuntimeError("database password should not leak")

    response = client.get("/test-only-error")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert not app.debug


def test_health_and_schema(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/").status_code == 200
    assert client.get("/openapi.json").status_code == 200
