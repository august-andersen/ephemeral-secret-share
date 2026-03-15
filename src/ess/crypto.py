import os
import base64

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def encrypt_secret(plaintext: str) -> tuple[str, str]:
    """Encrypt a secret with AES-256-GCM.

    Returns (ciphertext_b64, key_b64url) where:
    - ciphertext_b64: base64-encoded IV (12 bytes) + ciphertext + tag (16 bytes)
    - key_b64url: base64url-encoded 256-bit key (for the URL fragment)
    """
    key = os.urandom(32)
    iv = os.urandom(12)

    aesgcm = AESGCM(key)
    # AESGCM.encrypt returns ciphertext + tag concatenated
    ct_and_tag = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)

    # Store: IV + ciphertext + tag
    stored = iv + ct_and_tag
    ciphertext_b64 = base64.b64encode(stored).decode("ascii")
    key_b64url = base64.urlsafe_b64encode(key).decode("ascii").rstrip("=")

    return ciphertext_b64, key_b64url
