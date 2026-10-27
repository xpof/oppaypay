import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_WAF_KEY = bytes.fromhex("6f71a512b1e035eaab53d8be73120d3fb68a0ca346b9560aab3e5cdf753d5e98")
_aesgcm = AESGCM(_WAF_KEY)

def encrypt_waf(plaintext: bytes) -> str:
    iv = os.urandom(12)
    cipher_bytes = _aesgcm.encrypt(iv, plaintext, None)
    tag = cipher_bytes[-16:]
    ciphertext = cipher_bytes[:-16]
    iv_b64 = base64.b64encode(iv).decode('utf-8')
    return f"{iv_b64}::{tag.hex()}::{ciphertext.hex()}"