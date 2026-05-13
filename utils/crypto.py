import os
import hashlib
import base64
import json
from cryptography.fernet import Fernet


def _get_fernet() -> Fernet:
    raw_key = os.environ.get("DATA_ENCRYPTION_KEY", "")
    if not raw_key:
        raise RuntimeError(
            "DATA_ENCRYPTION_KEY is not set in .env — "
            "run `python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"` "
            "to generate one."
        )
    # Accept both raw Fernet keys and plain passphrases
    try:
        return Fernet(raw_key.encode())
    except Exception:
        # Derive a 32-byte key from a passphrase via SHA-256 → base64url
        derived = base64.urlsafe_b64encode(hashlib.sha256(raw_key.encode()).digest())
        return Fernet(derived)


def hash_email(email: str) -> str:
    """One-way hash so PII never appears as a storage key."""
    return hashlib.sha256(email.lower().strip().encode()).hexdigest()[:32]


def encrypt_record(record: dict) -> str:
    """Encrypt a dict → base64 ciphertext string."""
    f = _get_fernet()
    return f.encrypt(json.dumps(record).encode()).decode()


def decrypt_record(token: str) -> dict:
    """Decrypt a ciphertext string → dict."""
    f = _get_fernet()
    return json.loads(f.decrypt(token.encode()))
