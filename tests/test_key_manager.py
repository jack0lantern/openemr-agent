"""Unit tests for key_manager."""

import pytest
from pathlib import Path

from app.services.key_manager import (
    ensure_keys,
    private_key_to_jwks,
    JWK_KID,
)


class TestKeyManager:
    def test_ensure_keys_creates_keys_when_missing(self, tmp_path: Path):
        key_dir = tmp_path / "certs"
        key_path = key_dir / "private_key.pem"
        result = ensure_keys(key_dir, key_path)
        assert result == key_path
        assert key_path.exists()
        assert (key_dir / "public_key.pem").exists()
        assert key_path.read_bytes().startswith(b"-----BEGIN")

    def test_ensure_keys_returns_existing_key(self, tmp_path: Path):
        key_dir = tmp_path / "certs"
        key_path = key_dir / "private_key.pem"
        key_dir.mkdir(parents=True)
        key_path.write_bytes(b"-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----")
        result = ensure_keys(key_dir, key_path)
        assert result == key_path
        assert key_path.read_bytes() == b"-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"

    def test_private_key_to_jwks_returns_valid_structure(self, tmp_path: Path):
        # Use generate_jwks script's key format - we need a real key
        from app.services.key_manager import ensure_keys
        key_dir = tmp_path / "certs"
        key_path = key_dir / "private_key.pem"
        ensure_keys(key_dir, key_path)
        jwks = private_key_to_jwks(key_path)
        assert "keys" in jwks
        assert len(jwks["keys"]) == 1
        key = jwks["keys"][0]
        assert key["kty"] == "RSA"
        assert key["kid"] == JWK_KID
        assert key["alg"] == "RS384"
        assert "n" in key
        assert "e" in key
