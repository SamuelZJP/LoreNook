"""Password hashing with the standard library's scrypt; the parameters travel with each hash."""

import hashlib
import hmac
import secrets

N, R, P = 2 ** 15, 8, 1
MAX_MEMORY = 64 * 1024 * 1024


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P, maxmem=MAX_MEMORY)
    return f"scrypt${N}${R}${P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        kind, n, r, p, salt, digest = stored.split("$")
        if kind != "scrypt":
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p),
                                maxmem=MAX_MEMORY)
    except ValueError:
        return False
    return hmac.compare_digest(actual.hex(), digest)


# Compared against when the username is unknown, so both cases take the same time.
DUMMY_HASH = hash_password(secrets.token_hex(16))
