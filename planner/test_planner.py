import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize(("students", "expected"), [(0, 0), (20, 2), (21, 3)])
def test_groups(students, expected):
    response = client.get("/groups", params={"students": students, "group_size": 10})
    assert response.status_code == 200
    assert response.json() == {"groups": expected}


@pytest.mark.parametrize(("students", "size"), [(-1, 10), (10, 0)])
def test_invalid_input(students, size):
    assert (
        client.get("/groups", params={"students": students, "group_size": size}).status_code == 422
    )
