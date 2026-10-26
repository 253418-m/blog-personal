"""Hashing Argon2id sin políticas de entrada ni registro de credenciales."""

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError


class PasswordHasher:
    """Encapsula la configuración recomendada por pwdlib y su salt aleatorio."""

    def __init__(self) -> None:
        self._password_hash = PasswordHash.recommended()

    def hash_password(self, plain_password: str) -> str:
        if not isinstance(plain_password, str):
            raise TypeError("La contraseña debe ser texto.")
        return self._password_hash.hash(plain_password)

    def verify_password(self, plain_password: str, password_hash: str) -> bool:
        if not isinstance(plain_password, str) or not isinstance(password_hash, str):
            return False
        try:
            return self._password_hash.verify(plain_password, password_hash)
        except (UnknownHashError, UnicodeError):
            return False


_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    return _hasher.hash_password(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return _hasher.verify_password(plain_password, password_hash)
