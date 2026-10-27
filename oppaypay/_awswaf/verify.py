import hashlib
import base64
import itertools
import json
import random
import time
import uuid
import os
import yaml
from typing import Callable, Any, Tuple
from .crypto import encrypt_waf

def _check_pow(difficulty: int, hex_hash: str) -> bool:
    return int(hex_hash, 16) >> (len(hex_hash) * 4 - difficulty) == 0

def compute_scrypt_nonce(challenge_input: str, checksum: str, difficulty: int) -> str:
    salt = checksum.encode("utf-8")
    for nonce in itertools.count(0):
        password = (challenge_input + checksum + str(nonce)).encode("utf-8")
        hash_hex = hashlib.scrypt(password, salt=salt, n=128, r=8, p=1, dklen=16).hex()
        if _check_pow(difficulty, hash_hex):
            return str(nonce)

def hash_pow(challenge_input: str, checksum: str, difficulty: int) -> str:
    base = challenge_input + checksum
    nonce = 0
    while True:
        data = (base + str(nonce)).encode("utf-8")
        hash_bytes = hashlib.sha256(data).digest()
        parts = [f"{int.from_bytes(hash_bytes[i:i+4], byteorder='big'):08x}" for i in range(0, len(hash_bytes), 4)]
        if _check_pow(difficulty, "".join(parts)):
            return str(nonce)
        nonce += 1

def network_bandwidth(challenge_input: str, checksum: str, difficulty: int) -> str:
    sizes = {1: 1024, 2: 10 * 1024, 3: 100 * 1024, 4: 1048576, 5: 10 * 1048576}
    n = sizes.get(difficulty, 1024)
    return base64.b64encode(bytes(n)).decode("utf-8")

BANDWIDTH_CHALLENGE = "ha9faaffd31b4d5ede2a2e19d2d7fd525f66fee61911511960dcbb52d3c48ce25"
CHALLENGE_TYPES: dict[str, Callable[[Any, Any, Any], str]] = {
    "h72f957df656e80ba55f5d8ce2e8c7ccb59687dba3bfb273d54b08a261b2f3002": compute_scrypt_nonce,
    "h7b0c470f0cfe3a80a9e26526ad185f484f6817d0832712a4a37a908786a6a67f": hash_pow,
    BANDWIDTH_CHALLENGE: network_bandwidth,
}

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
    if result >= 0x80000000:
        result -= 0x100000000
    return result

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

_base_dir = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_base_dir, "webgl.yml"), "r", encoding="utf-8") as f:
    _webgl_data = yaml.safe_load(f)
    
GPUS = _webgl_data.get("gpus", [])

def get_fp(user_agent: str) -> Tuple[str, str]:

    ts = int(time.time() * 1000)
    
    is_ios = "iPhone" in user_agent or "iPad" in user_agent
    is_android = "Android" in user_agent
    is_mobile = is_ios or is_android
    
    if is_ios:
        candidate_gpus = [g for g in GPUS if g.get("platform") == "ios"]
    elif is_android:
        candidate_gpus = [g for g in GPUS if g.get("platform") == "android"]
    else:
        candidate_gpus = [g for g in GPUS if g.get("platform") in ("windows", "macos")]
        
    if not candidate_gpus:
        candidate_gpus = GPUS 
        
    gpu = random.choice(candidate_gpus)
    
    if is_ios:
        screen_res = "390-844-844-24-*-*-*"
    elif is_android:
        screen_res = "360-780-780-24-*-*-*"
    else:
        screen_res = "1920-1080-1032-24-*-*-*"

    bins = [random.randrange(0, 40) for _ in range(256)]
    bins[0], bins[-1] = random.randrange(14473, 16573), random.randrange(14473, 16573)

    fp = {
        "metrics": {"fp2": 1, "browser": 0, "capabilities": 1, "gpu": 7, "dnt": 0, "math": 0, "screen": 0, "navigator": 0, "auto": 1, "stealth": 0, "subtle": 0, "canvas": 5, "formdetector": 1, "be": 0},
        "start": ts,
        "flashVersion": None,
        "plugins": [
            {"name": "PDF Viewer", "str": "PDF Viewer "},
            {"name": "Chrome PDF Viewer", "str": "Chrome PDF Viewer "},
            {"name": "Chromium PDF Viewer", "str": "Chromium PDF Viewer "},
            {"name": "Microsoft Edge PDF Viewer", "str": "Microsoft Edge PDF Viewer "},
            {"name": "WebKit built-in PDF", "str": "WebKit built-in PDF "},
        ],
        "dupedPlugins": f"PDF Viewer Chrome PDF Viewer Chromium PDF Viewer Microsoft Edge PDF Viewer WebKit built-in PDF ||{screen_res}",
        "screenInfo": screen_res,
        "referrer": "",
        "userAgent": user_agent,
        "location": "",
        "webDriver": False,
        "capabilities": {
            "css": {"textShadow": 1, "WebkitTextStroke": 1, "boxShadow": 1, "borderRadius": 1, "borderImage": 1, "opacity": 1, "transform": 1, "transition": 1},
            "js": {"audio": True, "geolocation": random.choice([True, False]), "localStorage": "supported", "touch": is_mobile, "video": True, "webWorker": random.choice([True, False])},
            "elapsed": 1,
        },
        "gpu": {
            "vendor": gpu["vendor"],
            "model": gpu["model"],
            "extensions": gpu["extensions"].split(" "),
        },
        "dnt": None,
        "math": {"tan": "-1.4214488238747245", "sin": "0.8178819121159085", "cos": "-0.5753861119575491"},
        "automation": {"wd": {"properties": {"document": [], "window": [], "navigator": []}}, "phantom": {"properties": {"window": []}}},
        "stealth": {"t1": 0, "t2": 0, "i": 1, "mte": 0, "mtd": False},
        "crypto": {"crypto": 1, "subtle": 1, "encrypt": True, "decrypt": True, "wrapKey": True, "unwrapKey": True, "sign": True, "verify": True, "digest": True, "deriveBits": True, "deriveKey": True, "getRandomValues": True, "randomUUID": True},
        "canvas": {"hash": random.randrange(645172295, 735192295), "emailHash": None, "histogramBins": bins},
        "formDetected": False, "numForms": 0, "numFormElements": 0, "be": {"si": False},
        "end": ts + random.randint(1, 5),
        "errors": [],
        "version": "2.4.0",
        "id": str(uuid.uuid4()),
    }

    payload_str = json.dumps(fp, separators=(",", ":"))
    crc = _calculate_crc(payload_str)
    checksum = _encode_number(crc)
    encoded = f"{checksum}#{payload_str}"

    return checksum, encrypt_waf(encoded.encode("utf-8"))
