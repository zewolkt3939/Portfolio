from __future__ import annotations

import argparse
import getpass
import json
import secrets

import pyotp
from cryptography.fernet import Fernet


def init_db(_args) -> None:
    from .database import Base, engine

    Base.metadata.create_all(engine)
    print("Database schema is ready. Use Alembic migrations in production.")


def create_admin(args) -> None:
    from sqlalchemy import select

    from .database import SessionLocal
    from .models import AdminUser
    from .security import encrypt_totp, password_hasher

    username = (args.username or input("Username: ")).strip().casefold()
    password = getpass.getpass("Password (12+ characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if len(password) < 12 or password != confirmation:
        raise SystemExit("Password must have at least 12 characters and both values must match.")
    secret = pyotp.random_base32()
    recovery_codes = [secrets.token_hex(5) for _ in range(8)]
    with SessionLocal() as db:
        if db.scalar(select(AdminUser)):
            raise SystemExit("An admin account already exists. This CMS supports one admin.")
        user = AdminUser(
            username=username,
            password_hash=password_hasher.hash(password),
            totp_secret_encrypted=encrypt_totp(secret),
            recovery_codes_json=json.dumps([password_hasher.hash(code) for code in recovery_codes]),
        )
        db.add(user)
        db.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name="Bao Portfolio CMS")
    print("\nAdd this URI to your authenticator, then store the recovery codes offline:")
    print(uri)
    print("Recovery codes (each works once):")
    print("\n".join(recovery_codes))


def seed(_args) -> None:
    from .database import SessionLocal
    from .legacy import seed_legacy_posts

    with SessionLocal() as db:
        created, updated, skipped = seed_legacy_posts(db)
    print(f"Legacy migration complete: {created} created, {updated} updated, {skipped} unchanged.")


def fernet_key(_args) -> None:
    print(Fernet.generate_key().decode())


def main() -> None:
    parser = argparse.ArgumentParser(prog="portfolio-cms")
    sub = parser.add_subparsers(required=True)
    sub.add_parser("init-db", help="Create tables for local development").set_defaults(func=init_db)
    admin = sub.add_parser("create-admin", help="Create the only CMS administrator")
    admin.add_argument("--username")
    admin.set_defaults(func=create_admin)
    sub.add_parser("seed-legacy", help="Migrate the six existing research pages").set_defaults(func=seed)
    sub.add_parser("fernet-key", help="Generate FIELD_ENCRYPTION_KEY").set_defaults(func=fernet_key)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
