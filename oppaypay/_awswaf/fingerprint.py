import json
import random
import time
import uuid
import os
import ctypes
from .crypto import encrypt

ALPHABET = "0123456789abcdef"
IEEE_POLYNOMIAL = 0xEDB88320

def _build_crc_table() -> list:
    table = []
    for i in range(256):
        v = i
        for _ in range(8):
            if v & 1:
                v = (v >> 1) ^ IEEE_POLYNOMIAL
            else:
                v >>= 1
        table.append(v)
    return table

_CRC_TABLE = _build_crc_table()

def _calculate_crc(data: str) -> int:
    v = 0 ^ 0xFFFFFFFF
    for char in data:
        idx = 255 & (v ^ ord(char))
        v = (v & 0xFFFFFFFF) >> 8 ^ _CRC_TABLE[idx]
    result = 0xFFFFFFFF ^ v
    return ctypes.c_int32(result).value

def _encode_number(n: int) -> str:
    n = n & 0xFFFFFFFF
    return (
        ALPHABET[(n >> 28) & 15]
        + ALPHABET[(n >> 24) & 15]
        + ALPHABET[(n >> 20) & 15]
        + ALPHABET[(n >> 16) & 15]
        + ALPHABET[(n >> 12) & 15]
        + ALPHABET[(n >> 8) & 15]
        + ALPHABET[(n >> 4) & 15]
        + ALPHABET[n & 15]
    ).upper()

def get_fp(user_agent: str) -> str:
    timestamp = int(time.time() * 1000)
    
    webgl_data = {
        "vendor": "Google Inc. (NVIDIA)",
        "renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1080 Direct3D11 vs_5_0 ps_5_0, D3D11)"
    }
    
    canvas_hash = str(random.randint(100000, 999999))
    
    fp_data = {
        "ua": user_agent,
        "ts": timestamp,
        "webgl": webgl_data,
        "canvas": canvas_hash,
        "uuid": str(uuid.uuid4())
    }
    
    payload = json.dumps(fp_data, separators=(',', ':'))
    crc = _calculate_crc(payload)
    encoded_crc = _encode_number(crc)
    
    encrypted_payload = encrypt(payload.encode('utf-8'))
    
    return f"{encoded_crc}::{encrypted_payload}"