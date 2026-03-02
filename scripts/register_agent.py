#!/usr/bin/env python3
"""
Register the OpenEMR AI Agent with OpenEMR's OAuth2 dynamic client registration.
Generates RSA keys if missing, fetches scopes from discovery, and registers the client.
Use the returned client_id as OPENEMR_CLIENT_ID in .env.

Usage (from openemr-agent/ with venv activated):
  python scripts/register_agent.py
  python scripts/register_agent.py --force
  python scripts/register_agent.py --output-env

After registration, enable the client in Administration → System → API Clients.
"""

import argparse
import os
import sys
from pathlib import Path

# Add parent for app imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load .env before importing app modules
from dotenv import load_dotenv

load_dotenv()

from app.config import openemr_registration_url
from app.services.key_manager import ensure_keys, private_key_to_jwks
from app.services.oauth_registration import (
    _default_redirect_uri,
    get_all_supported_scopes_sync,
    register_agent,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Register OpenEMR AI Agent with OAuth2 dynamic client registration"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-register even if OPENEMR_CLIENT_ID is already set",
    )
    parser.add_argument(
        "--output-env",
        action="store_true",
        help="Print OPENEMR_CLIENT_ID=... for appending to .env",
    )
    parser.add_argument(
        "--key",
        default=None,
        help="Path to private key (default: PRIVATE_KEY_PATH or ./certs/private_key.pem)",
    )
    args = parser.parse_args()

    client_id = os.getenv("OPENEMR_CLIENT_ID", "")
    if client_id and not args.force:
        print("OPENEMR_CLIENT_ID is already set. Use --force to re-register.", file=sys.stderr)
        if args.output_env:
            print(f"OPENEMR_CLIENT_ID={client_id}")
        return 0

    key_path_str = args.key or os.getenv("PRIVATE_KEY_PATH", "./certs/private_key.pem")
    key_path = Path(key_path_str).resolve()
    key_dir = key_path.parent

    try:
        ensure_keys(key_dir, key_path)
    except Exception as e:
        print(f"Error ensuring keys: {e}", file=sys.stderr)
        return 1

    jwks = private_key_to_jwks(key_path)
    scope = get_all_supported_scopes_sync()
    registration_url = openemr_registration_url()
    redirect_uri = _default_redirect_uri()

    try:
        result = register_agent(registration_url, jwks, redirect_uri, scope)
    except Exception as e:
        print(f"Registration failed: {e}", file=sys.stderr)
        return 1

    new_client_id = result.get("client_id")
    if not new_client_id:
        print("Registration response missing client_id", file=sys.stderr)
        return 1

    reg_uri = result.get("registration_client_uri", "")
    print(f"Registered successfully. client_id={new_client_id}")
    if reg_uri:
        print(f"registration_client_uri={reg_uri}")
    print(
        "\nEnable the client in Administration → System → API Clients before using."
    )

    if args.output_env:
        print(f"\nOPENEMR_CLIENT_ID={new_client_id}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
