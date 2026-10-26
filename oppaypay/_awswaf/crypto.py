import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_KEY = bytes.fromhex("6f71a512b1e035eaab53d8be73120d3fb68a0ca346b9560aab3e5cdf753d5e98")
_AESGCM = AESGCM(_KEY)

def encrypt(plaintext: bytes) -> str:
    iv = os.urandom(12)
    cipher_bytes = _AESGCM.encrypt(iv, plaintext, None)
    tag = cipher_bytes[-16:]
    ciphertext = cipher_bytes[:-16]
    iv_b64 = base64.b64encode(iv).decode('utf-8')
    return f"{iv_b64}::{tag.hex()}::{ciphertext.hex()}"

def decrypt(encrypted: str) -> bytes:
    parts = encrypted.split("::")
    if len(parts) != 3:
        raise ValueError(f"Invalid encrypted format: expected 3 parts, got {len(parts)}")
    
    iv_b64, tag_hex, ct_hex = parts
    iv = base64.b64decode(iv_b64)
    tag = bytes.fromhex(tag_hex)
    ciphertext = bytes.fromhex(ct_hex)
    
    return _AESGCM.decrypt(iv, ciphertext + tag, None)