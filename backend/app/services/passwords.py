"""Password hashing and verification using salted PBKDF2-HMAC-SHA256."""

import hashlib
import secrets


# Work factor used when producing new password hashes.
ITERATIONS = 600_000


def hash_password(password: str) -> str:
    """Return a salted PBKDF2 hash string without retaining the raw password."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("ascii"),
        ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    """Check a password against the stored encoding using constant-time compare."""
    try:
        algorithm, iterations, salt, expected = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("ascii"),
            int(iterations),
        ).hex()
        return secrets.compare_digest(digest, expected)
    except (ValueError, TypeError):
        return False
