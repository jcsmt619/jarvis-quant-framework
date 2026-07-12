from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.moonshot.deterministic.br30a_secure_local_oauth_runtime_bridge import (
    ENVIRONMENT_SANDBOX,
    PROVIDER_TASTYTRADE_SANDBOX,
    KeyringCredentialVault,
    OAuthRuntimeCredentials,
    VaultUnavailableError,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Interactively store BR-30A OAuth credentials in the local OS credential vault."
    )
    parser.add_argument("--provider", choices=(PROVIDER_TASTYTRADE_SANDBOX,), default=PROVIDER_TASTYTRADE_SANDBOX)
    parser.add_argument("--environment", choices=(ENVIRONMENT_SANDBOX,), default=ENVIRONMENT_SANDBOX)
    args = parser.parse_args()

    print("BR-30A Secure Local OAuth Runtime Bridge")
    print("LIVE TRADING: DISABLED")
    print("Enter values only at the interactive prompts. Secret values are not echoed.")

    client_id = input("OAuth client identifier: ").strip()
    client_secret = getpass.getpass("Replacement OAuth client secret: ").strip()
    refresh_token = getpass.getpass("OAuth refresh token: ").strip()

    credentials = OAuthRuntimeCredentials(
        provider=args.provider,
        environment=args.environment,
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
    )
    try:
        KeyringCredentialVault().store_credentials(credentials)
    except (VaultUnavailableError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print("BR-30A OAuth credential setup complete.")
    print(f"provider={args.provider}")
    print(f"environment={args.environment}")
    print("credential_vault=local_os_vault")
    print("secret_values_printed=false")
    print("LIVE TRADING: DISABLED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
