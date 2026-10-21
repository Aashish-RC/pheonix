"""
Pheonix Vault CLI
Command-line interface for interacting with the encrypted vault.
"""

import argparse
import sys
import getpass
from pathlib import Path
from vault import KeyStoreManager

DEFAULT_VAULT_PATH = Path("vault.enc")


def get_manager(path: Path) -> KeyStoreManager:
    return KeyStoreManager(path)


def main():
    parser = argparse.ArgumentParser(description="Pheonix Vault CLI")
    parser.add_argument(
        "--vault",
        type=Path,
        default=DEFAULT_VAULT_PATH,
        help="Path to vault file (default: vault.enc)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Init
    init_parser = subparsers.add_parser("init", help="Initialize a new vault")

    # Set
    set_parser = subparsers.add_parser("set", help="Store or update a secret")
    set_parser.add_argument("key_id", help="Unique identifier for secret")
    set_parser.add_argument("--provider", default="custom", help="Provider name")
    set_parser.add_argument("--desc", default=None, help="Description")

    # Get
    get_parser = subparsers.add_parser("get", help="Retrieve a secret lease")
    get_parser.add_argument("key_id", help="Secret identifier")

    # List
    subparsers.add_parser("list", help="List stored secret identifiers and metadata")

    # Revoke
    revoke_parser = subparsers.add_parser("revoke", help="Revoke a secret")
    revoke_parser.add_argument("key_id", help="Secret identifier")
    revoke_parser.add_argument("--reason", default="Manual revocation", help="Revocation reason")

    # Rotate
    subparsers.add_parser("rotate", help="Rotate master vault passphrase")

    args = parser.parse_args()
    mgr = get_manager(args.vault)

    if args.command == "init":
        if mgr.is_initialized():
            print(f"Error: Vault already exists at {args.vault}")
            sys.exit(1)
        pwd = getpass.getpass("Enter master passphrase for new vault: ")
        pwd_confirm = getpass.getpass("Confirm master passphrase: ")
        if pwd != pwd_confirm:
            print("Error: Passphrases do not match.")
            sys.exit(1)
        mgr.initialize(pwd)
        print(f"Vault successfully initialized at {args.vault}")

    elif args.command == "set":
        pwd = getpass.getpass("Master passphrase: ")
        mgr.unlock(pwd)
        val = getpass.getpass(f"Enter secret value for '{args.key_id}': ")
        mgr.put_secret(args.key_id, val, provider=args.provider, description=args.desc)
        print(f"Secret '{args.key_id}' safely stored.")

    elif args.command == "get":
        pwd = getpass.getpass("Master passphrase: ")
        mgr.unlock(pwd)
        lease = mgr.get_lease(args.key_id)
        with lease:
            print(f"Secret value: {lease.get_plaintext()}")

    elif args.command == "list":
        pwd = getpass.getpass("Master passphrase: ")
        mgr.unlock(pwd)
        secrets = mgr.list_secrets()
        if not secrets:
            print("No secrets stored in vault.")
            return
        print(f"{'Key ID':<25} {'Provider':<15} {'Status':<12} {'Description'}")
        print("-" * 65)
        for s in secrets:
            status = "REVOKED" if s.revoked else "ACTIVE"
            print(f"{s.key_id:<25} {s.provider:<15} {status:<12} {s.description or ''}")

    elif args.command == "revoke":
        pwd = getpass.getpass("Master passphrase: ")
        mgr.unlock(pwd)
        if mgr.revoke_secret(args.key_id, reason=args.reason):
            print(f"Secret '{args.key_id}' successfully revoked.")
        else:
            print(f"Key ID '{args.key_id}' not found.")

    elif args.command == "rotate":
        pwd = getpass.getpass("Current master passphrase: ")
        mgr.unlock(pwd)
        new_pwd = getpass.getpass("New master passphrase: ")
        new_pwd_confirm = getpass.getpass("Confirm new passphrase: ")
        if new_pwd != new_pwd_confirm:
            print("Error: Passphrases do not match.")
            sys.exit(1)
        mgr.rotate_passphrase(new_pwd)
        print("Vault master passphrase rotated successfully.")


if __name__ == "__main__":
    main()
