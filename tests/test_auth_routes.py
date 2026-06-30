def test_login_happy_path_sets_cookies(client, password):
    resp = client.post("/api/auth/login", json={"username": "mrahuja", "password": password})
    assert resp.status_code == 200
    assert resp.json()["data"]["username"] == "mrahuja"
    cookies = resp.cookies
    assert "session" in cookies
    assert "csrf" in cookies


def test_login_wrong_password_rejected(client):
    resp = client.post("/api/auth/login", json={"username": "mrahuja", "password": "nope"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "auth_error"


def test_login_lockout_after_five_fails(client):
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "mrahuja", "password": "nope"})
    # 6th attempt — even with correct creds — is locked out
    resp = client.post("/api/auth/login", json={"username": "mrahuja", "password": "anything"})
    assert resp.status_code == 403
    assert "locked" in resp.json()["error"]["message"].lower()


def test_me_requires_auth(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_user_when_authed(auth_client):
    resp = auth_client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["data"]["username"] == "mrahuja"


def test_logout_requires_csrf(auth_client):
    # No X-CSRF-Token header -> 403
    resp = auth_client.post("/api/auth/logout")
    assert resp.status_code == 403


def test_logout_with_csrf(auth_client):
    csrf = auth_client.cookies.get("csrf")
    resp = auth_client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 200
