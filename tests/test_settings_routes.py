def _csrf(client):
    return {"X-CSRF-Token": client.cookies.get("csrf")}


def test_settings_requires_auth(client):
    assert client.get("/api/settings").status_code == 401


def test_put_then_get_settings_roundtrip_secret_never_returned(auth_client):
    resp = auth_client.put(
        "/api/settings",
        json={"api_key": "key_abc", "api_secret": "secret_xyz"},
        headers=_csrf(auth_client),
    )
    assert resp.status_code == 200

    got = auth_client.get("/api/settings").json()["data"]
    assert got["kite_api_key"] == "key_abc"
    assert got["kite_api_secret_set"] is True
    # The secret must NEVER appear in the response body.
    assert "secret_xyz" not in resp.text
    assert "kite_api_secret" not in got


def test_resaving_without_secret_keeps_existing(auth_client):
    auth_client.put(
        "/api/settings",
        json={"api_key": "key_abc", "api_secret": "secret_xyz"},
        headers=_csrf(auth_client),
    )
    # Re-save with a new key but no secret.
    auth_client.put(
        "/api/settings",
        json={"api_key": "key_def"},
        headers=_csrf(auth_client),
    )
    got = auth_client.get("/api/settings").json()["data"]
    assert got["kite_api_key"] == "key_def"
    assert got["kite_api_secret_set"] is True  # secret retained


def test_put_settings_requires_csrf(auth_client):
    resp = auth_client.put("/api/settings", json={"api_key": "x"})
    assert resp.status_code == 403
