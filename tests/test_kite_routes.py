from core.clock import today_ist


def _csrf(client):
    return {"X-CSRF-Token": client.cookies.get("csrf")}


def _set_creds(auth_client):
    auth_client.put(
        "/api/settings",
        json={"api_key": "key_abc", "api_secret": "secret_xyz"},
        headers=_csrf(auth_client),
    )


def test_callback_stores_session_and_status_reflects(auth_client, monkeypatch):
    _set_creds(auth_client)

    async def fake_exchange(session, request_token):
        assert request_token == "req_token_123"
        return {"access_token": "ACCESS_TOKEN_VALUE", "user_id": "AB1234"}

    monkeypatch.setattr("api.routes.kite.exchange", fake_exchange)

    resp = auth_client.get(
        "/api/kite/callback",
        params={"request_token": "req_token_123", "status": "success"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/?kite=connected"

    status = auth_client.get("/api/kite/status").json()["data"]
    assert status["connected"] is True
    assert status["user_id"] == "AB1234"
    assert status["valid_for_date"] == today_ist()


def test_callback_failure_status_rejected(auth_client):
    resp = auth_client.get(
        "/api/kite/callback",
        params={"request_token": "x", "status": "failed"},
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "kite_error"


def test_status_requires_auth(client):
    assert client.get("/api/kite/status").status_code == 401


def test_postback_stub_returns_ok(client):
    resp = client.post("/api/kite/postback", json={"order_id": "1"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_health(client):
    data = client.get("/api/health").json()["data"]
    assert data["status"] == "ok"
    assert data["env"] == "dev"
