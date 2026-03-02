"""
Key management for OpenEMR OAuth2 private_key_jwt authentication.
Generates RSA key pairs and derives JWKS for client registration.
"""

import base64
import logging
from pathlib import Path

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

logger = logging.getLogger(__name__)

JWK_KID = "ai-agent-key"


def _base64url_encode(data: bytes) -> str:
    """Base64url encode without padding (RFC 4648)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _int_to_big_endian_bytes(n: int) -> bytes:
    """Convert integer to unsigned big-endian bytes (minimal length)."""
    if n == 0:
        return b"\x00"
    bit_length = n.bit_length()
    byte_length = (bit_length + 7) // 8
    return n.to_bytes(byte_length, "big")


def private_key_to_jwks(private_key_path: Path, kid: str = JWK_KID) -> dict:
    """Load private key and return JWKS dict with public key."""
    pem = private_key_path.read_bytes()
    private_key = serialization.load_pem_private_key(
        pem, password=None, backend=default_backend()
    )

    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise ValueError("Key must be RSA")

    public_numbers = private_key.public_key().public_numbers()
    n_bytes = _int_to_big_endian_bytes(public_numbers.n)
    e_bytes = _int_to_big_endian_bytes(public_numbers.e)

    jwk = {
        "kty": "RSA",
        "kid": kid,
        "use": "sig",
        "alg": "RS384",
        "n": _base64url_encode(n_bytes),
        "e": _base64url_encode(e_bytes),
    }

    return {"keys": [jwk]}


def ensure_keys(key_dir: Path, private_key_path: Path) -> Path:
    """
    Ensure RSA key pair exists. If private_key_path does not exist,
    generate 4096-bit RSA key pair and write to key_dir.
    Returns path to private key.
    """
    if private_key_path.exists():
        logger.info("ensure_keys: private key already exists at %s", private_key_path)
        return private_key_path

    logger.info("ensure_keys: generating new 4096-bit RSA key pair in %s", key_dir)
    key_dir.mkdir(parents=True, exist_ok=True)

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
        backend=default_backend(),
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_key_path.write_bytes(private_pem)
    public_key_path = key_dir / "public_key.pem"
    public_key_path.write_bytes(public_pem)

    logger.info("ensure_keys: generated RSA key pair at %s and %s", private_key_path, public_key_path)
    return private_key_path
