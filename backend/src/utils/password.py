"""PBKDF2-SHA256 password hashing (stdlib only, no native wheel needed).

Demo accounts share ``Demo@2026``; seed passes an empty salt so the stored hash
is stable across seed runs (idempotent upsert by natural key).
"""
import hashlib
import hmac
import secrets

ITERATIONS = 120_000
DEMO_PASSWORD = "Demo@2026"


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, expected = stored.split("$")
    except (ValueError, AttributeError):
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))
    return hmac.compare_digest(digest.hex(), expected)
