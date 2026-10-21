import json

import pyotp

from portfolio_cms.config import Settings
from portfolio_cms.models import AdminUser, LoginAttempt
from portfolio_cms.security import (
    create_session,
    encrypt_totp,
    load_session,
    login_is_limited,
    password_hasher,
    verify_totp_or_recovery,
)


def settings(tmp_path):
    return Settings(
        database_url="sqlite://",
        app_secret_key="test-secret-that-is-long-enough-for-tests",
        field_encryption_key="",
        upload_dir=tmp_path,
    )


def test_totp_recovery_and_hashed_session(db, tmp_path):
    cfg = settings(tmp_path)
    secret = pyotp.random_base32()
    recovery = "alpha-bravo-charlie"
    user = AdminUser(
        username="bao",
        password_hash=password_hasher.hash("a-strong-test-password"),
        totp_secret_encrypted=encrypt_totp(secret, cfg),
        recovery_codes_json=json.dumps([password_hasher.hash(recovery)]),
    )
    db.add(user)
    db.commit()
    assert verify_totp_or_recovery(db, user, pyotp.TOTP(secret).now(), cfg)
    assert verify_totp_or_recovery(db, user, recovery, cfg)
    assert not verify_totp_or_recovery(db, user, recovery, cfg)

    raw, session = create_session(db, user, True, cfg)
    assert raw not in session.token_hash
    assert load_session(db, raw, settings=cfg).user_id == user.id


def test_rate_limit_after_five_failures(db, tmp_path):
    cfg = settings(tmp_path)
    subject = "fixed-subject"
    for _ in range(5):
        db.add(LoginAttempt(subject_hash=subject, successful=False))
    db.commit()
    assert login_is_limited(db, subject, cfg)
