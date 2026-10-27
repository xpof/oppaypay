import os
import base64
import logging
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

log = logging.getLogger(__name__)

DEFAULT_KEY = bytes.fromhex("6f71a512b1e035eaab53d8be73120d3fb68a0ca346b9560aab3e5cdf753d5e98")
_current_key = DEFAULT_KEY
_aesgcm = AESGCM(_current_key)

def set_encryption_key(key: bytes):
    global _current_key, _aesgcm
    _current_key = key
    _aesgcm = AESGCM(key)

def update_key_from_goku_props(goku_props: dict):
    """goku_props から動的に鍵を取得するフォールバック"""
    try:
        if "key" in goku_props:
            key_hex = goku_props["key"]
            if isinstance(key_hex, str) and len(key_hex) == 64:
                set_encryption_key(bytes.fromhex(key_hex))
                log.info("WAF encryption key updated from goku_props")
    except Exception as e:
        log.warning(f"Failed to update WAF key: {e}")

def encrypt_waf(plaintext: bytes) -> str:
    iv = os.urandom(12)
    cipher_bytes = _aesgcm.encrypt(iv, plaintext, None)
    tag = cipher_bytes[-16:]
    ciphertext = cipher_bytes[:-16]
    iv_b64 = base64.b64encode(iv).decode('utf-8')
    return f"{iv_b64}::{tag.hex()}::{ciphertext.hex()}"
