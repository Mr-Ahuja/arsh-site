from core.crypto import decrypt, encrypt


def test_encrypt_decrypt_roundtrip():
    secret = "some-app-secret"
    plain = "super-secret-token-value"
    enc = encrypt(plain, secret)
    assert enc != plain
    assert decrypt(enc, secret) == plain
