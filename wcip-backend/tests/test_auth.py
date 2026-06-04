"""Authentication & authorization API tests."""


def test_register_and_login(client):
    r = client.post("/api/v1/auth/register",
                    json={"email": "u1@example.com", "password": "password123"})
    assert r.status_code == 201
    assert r.json()["email"] == "u1@example.com"

    tok = client.post("/api/v1/auth/login",
                      data={"username": "u1@example.com", "password": "password123"})
    assert tok.status_code == 200
    body = tok.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]


def test_duplicate_email_rejected(client):
    client.post("/api/v1/auth/register",
                json={"email": "dup@example.com", "password": "password123"})
    r = client.post("/api/v1/auth/register",
                    json={"email": "dup@example.com", "password": "password123"})
    assert r.status_code == 409


def test_login_wrong_password(client):
    client.post("/api/v1/auth/register",
                json={"email": "wp@example.com", "password": "password123"})
    r = client.post("/api/v1/auth/login",
                    data={"username": "wp@example.com", "password": "nope"})
    assert r.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_with_token(client, auth_headers):
    r = client.get("/api/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert "email" in r.json()


def test_refresh_flow(client):
    client.post("/api/v1/auth/register",
                json={"email": "rf@example.com", "password": "password123"})
    tok = client.post("/api/v1/auth/login",
                      data={"username": "rf@example.com", "password": "password123"}).json()
    r = client.post("/api/v1/auth/refresh",
                    json={"refresh_token": tok["refresh_token"]})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_admin_endpoint_forbidden_for_user(client, auth_headers):
    assert client.get("/api/v1/admin/analytics", headers=auth_headers).status_code == 403
