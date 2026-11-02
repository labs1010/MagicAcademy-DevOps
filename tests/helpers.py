from app.models import User
from app.security import hash_password

PASSWORD = "Student-test-password-42"


def register(client, username):
    response = client.post("/auth/register", json={"username": username, "password": PASSWORD})
    assert response.status_code == 201, response.text
    return response.json()


def headers(client, username):
    response = client.post("/auth/token", data={"username": username, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def admin(app, client):
    with app.state.session_factory() as db:
        db.add(User(username="admin", password_hash=hash_password(PASSWORD), role="ADMIN"))
        db.commit()
    return headers(client, "admin")
