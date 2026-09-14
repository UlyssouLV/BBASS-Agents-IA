import hashlib
import hmac
import os

_ALGORITHM = "sha256"
_ITERATIONS = 600_000
_SALT_BYTES = 16


def hash_password(mot_de_passe: str) -> str:
    salt = os.urandom(_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(_ALGORITHM, mot_de_passe.encode("utf-8"), salt, _ITERATIONS)
    return f"{_ALGORITHM}${_ITERATIONS}${salt.hex()}${derived.hex()}"


def verify_password(mot_de_passe: str, mot_de_passe_hash: str) -> bool:
    try:
        algorithm, iterations_str, salt_hex, derived_hex = mot_de_passe_hash.split("$")
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(derived_hex)
    except (ValueError, AttributeError):
        return False

    candidate = hashlib.pbkdf2_hmac(algorithm, mot_de_passe.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)
