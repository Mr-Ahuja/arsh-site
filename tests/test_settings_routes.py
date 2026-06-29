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


# --- Telegram settings ---

def test_get_settings_includes_telegram_fields(auth_client):
    got = auth_client.get("/api/settings").json()["data"]
    assert "telegram_bot_token_set" in got
    assert "telegram_chat_id" in got
    assert got["telegram_bot_token_set"] is False
    assert got["telegram_chat_id"] == ""


def test_telegram_roundtrip_token_never_returned(auth_client):
    resp = auth_client.put(
        "/api/settings/telegram",
        json={"bot_token": "9999:AAAA_secret_token", "chat_id": "-100123456"},
        headers=_csrf(auth_client),
    )
    assert resp.status_code == 200

    got = auth_client.get("/api/settings").json()["data"]
    assert got["telegram_bot_token_set"] is True
    assert got["telegram_chat_id"] == "-100123456"
    # Token must NEVER appear anywhere in any response.
    assert "AAAA_secret_token" not in resp.text
    assert "bot_token" not in got


def test_telegram_resave_without_token_keeps_existing(auth_client):
    auth_client.put(
        "/api/settings/telegram",
        json={"bot_token": "9999:original_token", "chat_id": "-100111"},
        headers=_csrf(auth_client),
    )
    # Update chat_id only — token should survive.
    auth_client.put(
        "/api/settings/telegram",
        json={"chat_id": "-100999"},
        headers=_csrf(auth_client),
    )
    got = auth_client.get("/api/settings").json()["data"]
    assert got["telegram_bot_token_set"] is True
    assert got["telegram_chat_id"] == "-100999"


def test_telegram_put_requires_csrf(auth_client):
    resp = auth_client.put("/api/settings/telegram", json={"chat_id": "x"})
    assert resp.status_code == 403


def test_telegram_test_requires_config_when_no_inline_creds(auth_client):
    # No DB config and no inline credentials → 422.
    resp = auth_client.post(
        "/api/settings/telegram/test",
        json={},
        headers=_csrf(auth_client),
    )
    assert resp.status_code == 422


def test_telegram_test_requires_csrf(auth_client):
    resp = auth_client.post("/api/settings/telegram/test", json={})
    assert resp.status_code == 403
