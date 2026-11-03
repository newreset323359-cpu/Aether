import pytest
from app.security.auth import hash_password, verify_password, create_access_token, decode_access_token

def test_password_hash_roundtrip():
    hashed=hash_password("A-strong-password-123")
    assert hashed != "A-strong-password-123"
    assert verify_password("A-strong-password-123",hashed)
    assert not verify_password("wrong-password",hashed)

def test_password_minimum_length():
    with pytest.raises(ValueError):
        hash_password("short")

def test_signed_token_roundtrip(monkeypatch):
    monkeypatch.setenv("AETHER_JWT_SECRET","x"*64)
    token=create_access_token(7,"suraj",True)
    claims=decode_access_token(token)
    assert claims["sub"]=="7" and claims["admin"] is True
    parts=token.split(".")
    tampered=parts[0]+"."+parts[1]+"."+"A"*43
    with pytest.raises(Exception):
        decode_access_token(tampered)
