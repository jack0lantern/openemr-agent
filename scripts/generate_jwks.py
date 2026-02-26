#!/usr/bin/env python3
"""
Generate JWKS (JSON Web Key Set) from the ai-agent's private key.
Use the output to register/update the OpenEMR OAuth client with inline jwks.

Usage (from openemr-agent/ with venv activated):
  python scripts/generate_jwks.py
  # Or with custom key path:
  python scripts/generate_jwks.py --key ./certs/private_key.pem

Output: JSON suitable for the "jwks" field in OAuth client registration.

Alternative: Use https://russelldavies.github.io/jwk-creator/ — paste your public key
  (openssl rsa -in certs/private_key.pem -pubout) and set kid to "ai-agent-key".
"""
# AI-generated: JWKS generator for OpenEMR OAuth client registration

import argparse
import base64
import json
import sys
from pathlib import Path

# Add parent path for app imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend


def base64url_encode(data: bytes) -> str:
    """Base64url encode without padding (RFC 4648)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def int_to_big_endian_bytes(n: int) -> bytes:
    """Convert integer to unsigned big-endian bytes (minimal length)."""
    if n == 0:
        return b"\x00"
    bit_length = n.bit_length()
    byte_length = (bit_length + 7) // 8
    return n.to_bytes(byte_length, "big")


def private_key_to_jwks(private_key_path: Path, kid: str = "ai-agent-key") -> dict:
    """Load private key and return JWKS dict with public key."""
    pem = private_key_path.read_bytes()
    private_key = serialization.load_pem_private_key(pem, password=None, backend=default_backend())

    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise ValueError("Key must be RSA")

    public_numbers = private_key.public_key().public_numbers()
    n_bytes = int_to_big_endian_bytes(public_numbers.n)
    e_bytes = int_to_big_endian_bytes(public_numbers.e)

    jwk = {
        "kty": "RSA",
        "kid": kid,
        "use": "sig",
        "alg": "RS384",
        "n": base64url_encode(n_bytes),
        "e": base64url_encode(e_bytes),
    }

    return {"keys": [jwk]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate JWKS from private key")
    parser.add_argument(
        "--key",
        default="./certs/private_key.pem",
        help="Path to private key PEM file",
    )
    parser.add_argument(
        "--kid",
        default="ai-agent-key",
        help="Key ID (must match fhir_client.py JWT header)",
    )
    args = parser.parse_args()

    key_path = Path(args.key)
    if not key_path.exists():
        print(f"Error: Key file not found: {key_path}", file=sys.stderr)
        sys.exit(1)

    jwks = private_key_to_jwks(key_path, kid=args.kid)
    print(json.dumps(jwks, indent=2))


if __name__ == "__main__":
    main()
# End AI-generated code
