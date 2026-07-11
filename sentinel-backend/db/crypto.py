import os
import base64
from cryptography.fernet import Fernet

# A default key for fallback (must be 32 base64-encoded bytes)
DEFAULT_KEY = base64.urlsafe_b64encode(b"kavach_secret_encryption_key_32b")

# Retrieve key from environment or fallback
ENCRYPTION_KEY = os.environ.get("KAVACH_ENCRYPTION_KEY", "").encode()
if not ENCRYPTION_KEY:
    ENCRYPTION_KEY = DEFAULT_KEY
else:
    # Ensure it's valid base64url-encoded 32 bytes
    try:
        Fernet(ENCRYPTION_KEY)
    except Exception:
        # If invalid, derive key or pad it
        import hashlib
        derived = hashlib.sha256(ENCRYPTION_KEY).digest()
        ENCRYPTION_KEY = base64.urlsafe_b64encode(derived)

fernet = Fernet(ENCRYPTION_KEY)

def encrypt_val(val: str) -> str:
    """Encrypt a string value using AES-128/256 Fernet."""
    if not val:
        return val
    return fernet.encrypt(val.strip().upper().encode()).decode()

def decrypt_val(val: str) -> str:
    """Decrypt a string value using Fernet. If it fails, returns as-is for resilience."""
    if not val:
        return val
    try:
        return fernet.decrypt(val.strip().encode()).decode()
    except Exception:
        # Fallback in case of raw unencrypted data during migration or testing
        return val
