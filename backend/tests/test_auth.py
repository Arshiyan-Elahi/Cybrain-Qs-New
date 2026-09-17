import uuid


def test_register_returns_token(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"a-{uuid.uuid4().hex[:6]}@example.com", "password": "passphrase123", "fullName": "A"},
    )
    assert response.status_code == 201
    assert response.json()["accessToken"]


def test_duplicate_email_conflicts(client):
    email = f"dup-{uuid.uuid4().hex[:6]}@example.com"
    payload = {"email": email, "password": "passphrase123", "fullName": "A"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_short_password_rejected(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "x@example.com", "password": "short", "fullName": "A"},
    )
    assert response.status_code == 422


def test_login_wrong_password_is_indistinguishable(client):
    email = f"e-{uuid.uuid4().hex[:6]}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "passphrase123", "fullName": "A"},
    )
    wrong = client.post("/api/v1/auth/login", json={"email": email, "password": "nope12345"})
    missing = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "nope12345"}
    )
    assert wrong.status_code == missing.status_code == 401
    # Identical message, so the endpoint cannot be used to enumerate accounts.
    assert wrong.json()["error"]["message"] == missing.json()["error"]["message"]


def test_me_requires_authentication(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_rejects_garbage_token(client):
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 401


def test_me_returns_current_user(client, auth_headers):
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert "@" in response.json()["email"]


def test_error_response_carries_request_id(client):
    response = client.get("/api/v1/auth/me")
    assert response.json()["requestId"]
    assert response.headers["X-Request-ID"]
def test_demo_local_email_can_reach_authentication(client, db_session):
    from app.core.security import hash_password
    from app.modules.auth.models import User

    db_session.add(User(email="demo@cybrain.local", hashed_password=hash_password("CybrainDemo123!"),
                        full_name="Demo QA Reviewer", is_active=True))
    db_session.flush()

    response = client.post("/api/v1/auth/login", json={
        "email": "demo@cybrain.local", "password": "CybrainDemo123!"
    })

    assert response.status_code == 200
    assert response.json()["tokenType"] == "bearer"
    assert response.json()["accessToken"]
    me = client.get("/api/v1/auth/me", headers={
        "Authorization": f"Bearer {response.json()['accessToken']}"
    })
    assert me.status_code == 200
    assert me.json()["email"] == "demo@cybrain.local"
