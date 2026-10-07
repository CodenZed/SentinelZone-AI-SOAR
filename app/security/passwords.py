"""Salted PBKDF2-SHA256; no password or login credential is logged."""

import hashlib
import secrets

ITERATIONS = 600_000


def hash_password(password):
    if not 14 <= len(password) <= 256:
        raise ValueError("Password length must be 14 to 256 characters")
    salt = secrets.token_bytes(16)
    result = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${result.hex()}"


def verify_password(password, encoded):
    try:
        algorithm, rounds, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256" or int(rounds) != ITERATIONS:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return secrets.compare_digest(actual.hex(), expected)
    except (ValueError, AttributeError):
        return False
