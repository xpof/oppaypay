import re
import json
import base64
import random
import logging
import time
import hashlib
from urllib.parse import urlparse, urlunparse
from curl_cffi import requests, CurlMime
from .verify import CHALLENGE_TYPES, BANDWIDTH_CHALLENGE, get_fp
from .crypto import update_key_from_goku_props, set_encryption_key
from .._fingerprint import select_profile

log = logging.getLogger(__name__)


class AwsWafSolver:

    _cached_key: bytes | None = None
    _key_extracted_at: float = 0.0
    _KEY_TTL_SECONDS = 3600  

    def __init__(self, goku_props: dict, challenge_url: str, domain: str, user_agent: str):
        self.goku_props = goku_props
        self.challenge_url = challenge_url
        self.domain = domain
        self.user_agent = user_agent

        profile = select_profile(user_agent)
        log.debug(f"Using TLS profile: {profile} (UA: {user_agent[:60]}...)")

        self.session = requests.Session(
            impersonate=profile,
            http2=True,           
            timeout=15,
        )

        is_ios = "iPhone" in user_agent or "iPad" in user_agent
        is_android = "Android" in user_agent

        if is_ios:
            sec_ch_ua_platform = '"iOS"'
            sec_ch_ua = '"Not/A)Brand";v="99", "Safari";v="26", "WebKit";v="605"'
            sec_ch_ua_mobile = "?1"
        elif is_android:
            sec_ch_ua_platform = '"Android"'
            sec_ch_ua = '"Not A(Brand";v="8", "Chromium";v="132"'
            sec_ch_ua_mobile = "?1"
        else:
            sec_ch_ua_platform = '"Windows"'
            sec_ch_ua = '"Not A(Brand";v="8", "Chromium";v="132"'
            sec_ch_ua_mobile = "?0"

        self.session.headers = {
            "connection": "keep-alive",
            "sec-ch-ua-platform": sec_ch_ua_platform,
            "user-agent": user_agent,
            "sec-ch-ua": sec_ch_ua,
            "sec-ch-ua-mobile": sec_ch_ua_mobile,
            "accept": "*/*",
            "sec-fetch-site": "cross-site",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "ja-JP,ja;q=0.9",
        }

        parsed = urlparse(challenge_url)
        base_path = parsed.path.rsplit("/", 1)[0] if "/" in parsed.path else ""
        self.inputs_url = urlunparse(
            (parsed.scheme, parsed.netloc, f"{base_path}/inputs", "", "client=browser", "")
        )
        self.base_verify_url = challenge_url.rsplit("/challenge.js", 1)[0]

    def _extract_key_from_challenge_js(self) -> bytes | None:
        now = time.time()
        if self._cached_key is not None and (now - self._key_extracted_at) < self._KEY_TTL_SECONDS:
            log.debug("Using cached encryption key")
            return self._cached_key

        try:
            log.debug(f"Fetching challenge.js for key extraction: {self.challenge_url}")
            res = self.session.get(self.challenge_url, timeout=10)
            if res.status_code != 200:
                log.warning(f"challenge.js fetch failed: HTTP {res.status_code}")
                return None

            js = res.text
            key = self._parse_key_from_js(js)
            if key:
                self.__class__._cached_key = key
                self.__class__._key_extracted_at = now
                set_encryption_key(key)
                log.info(f"Encryption key extracted from challenge.js ({key.hex()[:16]}...)")
                return key
            else:
                log.debug("No key pattern found in challenge.js")
                return None
        except Exception as e:
            log.warning(f"Key extraction from challenge.js failed: {e}")
            return None

    @staticmethod
    def _parse_key_from_js(js: str) -> bytes | None:

        patterns = [
            r'["\']([0-9a-fA-F]{64})["\']',                 
            r'key\s*[:=]\s*["\']([0-9a-fA-F]{64})["\']',    
            r'Uint8Array\(\s*\[([0-9,\sx]+)\]\s*\)',         
        ]

        for pat in patterns[:2]:
            m = re.search(pat, js)
            if m:
                try:
                    key = bytes.fromhex(m.group(1))
                    if len(key) == 32:
                        return key
                except Exception:
                    pass

        m = re.search(r'Uint8Array\(\s*\[([0-9,\sx]+)\]\s*\)', js)
        if m:
            try:
                hex_bytes = re.findall(r'0x([0-9a-fA-F]{1,2})', m.group(1))
                if len(hex_bytes) == 32:
                    return bytes(int(h, 16) for h in hex_bytes)
                dec_bytes = re.findall(r'\b(\d{1,3})\b', m.group(1))
                if len(dec_bytes) == 32:
                    return bytes(int(d) for d in dec_bytes)
            except Exception:
                pass

        return None

    def _ensure_key(self):
        if isinstance(self.goku_props, dict) and "key" in self.goku_props:
            try:
                update_key_from_goku_props(self.goku_props)
                log.debug("Encryption key updated from goku_props")
                return
            except Exception as e:
                log.debug(f"goku_props key failed: {e}")

        extracted = self._extract_key_from_challenge_js()
        if extracted:
            return

        log.debug("Falling back to default encryption key")

    def get_inputs(self) -> dict:
        res = self.session.get(self.inputs_url)
        try:
            data = res.json()
        except Exception:
            raise Exception(f"inputs returned non-JSON (HTTP {res.status_code}): {res.text[:300]}")
        if "code" in data and "message" in data:
            raise Exception(f"inputs rejected: code={data['code']}, message={data['message']}")
        return data

    def _extract_challenge_meta(self, inputs: dict) -> tuple:
        challenge_type = inputs.get("challenge_type")
        difficulty = inputs.get("difficulty")

        if not challenge_type:
            try:
                raw_input = inputs.get("challenge", {}).get("input", "")
                if raw_input:
                    padded = raw_input + "=" * (-len(raw_input) % 4)
                    decoded = base64.b64decode(padded).decode("utf-8")
                    inner = json.loads(decoded)
                    challenge_type = inner.get("challenge_type")
                    if difficulty is None:
                        difficulty = inner.get("difficulty")
                    log.info(f"Extracted challenge_type='{challenge_type}' from decoded challenge.input")
            except Exception as e:
                log.debug(f"Failed to decode challenge.input: {e}")

        if not challenge_type:
            raise ValueError(f"challenge_type not found in inputs. Keys: {list(inputs.keys())}")
        if difficulty is None:
            raise ValueError(f"difficulty not found in inputs. Keys: {list(inputs.keys())}")
        return challenge_type, difficulty

    def build_payload(self, inputs: dict):
        challenge_type, difficulty = self._extract_challenge_meta(inputs)
        verify_func = CHALLENGE_TYPES.get(challenge_type)
        if not verify_func:
            raise ValueError(f"Unknown challenge type: {challenge_type}")

        checksum, fp = get_fp(self.session.headers["user-agent"])
        is_mp = (challenge_type == BANDWIDTH_CHALLENGE)

        if is_mp:
            solution_data = verify_func(inputs["challenge"]["input"], checksum, difficulty)
            solution_in_metadata = None
        else:
            solution_data = None
            solution_in_metadata = verify_func(inputs["challenge"]["input"], checksum, difficulty)

        payload = {
            "challenge": inputs["challenge"],
            "checksum": checksum,
            "solution": solution_in_metadata,
            "signals": [{"name": "Zoey", "value": {"Present": fp}}],
            "existing_token": None,
            "client": "Browser",
            "domain": self.domain,
            "metrics": [
                {"name": "2", "value": round(random.uniform(0.5, 3.0), 13), "unit": "2"},
                {"name": "100", "value": 1, "unit": "2"},
                {"name": "101", "value": 1, "unit": "2"},
                {"name": "102", "value": 1, "unit": "2"},
                {"name": "103", "value": random.randint(8, 12), "unit": "2"},
                {"name": "104", "value": 0, "unit": "2"},
                {"name": "105", "value": 0, "unit": "2"},
                {"name": "106", "value": 0, "unit": "2"},
                {"name": "107", "value": 0, "unit": "2"},
                {"name": "108", "value": 1, "unit": "2"},
                {"name": "undefined", "value": 1, "unit": "2"},
                {"name": "110", "value": 0, "unit": "2"},
                {"name": "111", "value": random.randint(20, 35), "unit": "2"},
                {"name": "112", "value": random.randint(1, 3), "unit": "2"},
                {"name": "undefined", "value": 1, "unit": "2"},
                {"name": "3", "value": round(random.uniform(8.0, 16.0), 15), "unit": "2"},
                {"name": "7", "value": 0, "unit": "4"},
                {"name": "1", "value": round(random.uniform(50.0, 90.0), 1), "unit": "2"},
                {"name": "4", "value": round(random.uniform(4.0, 8.0), 13), "unit": "2"},
                {"name": "5", "value": round(random.uniform(0.3, 1.5), 13), "unit": "2"},
                {"name": "6", "value": round(random.uniform(60.0, 90.0), 14), "unit": "2"},
                {"name": "8", "value": 1, "unit": "4"},
            ],
            "goku_props": self.goku_props,
        }
        return payload, solution_data, is_mp

    def solve(self, max_retries=3):
        self._ensure_key()

        for attempt in range(max_retries):
            try:
                inputs = self.get_inputs()
                payload, solution_data, is_mp = self.build_payload(inputs)
                if is_mp:
                    return self._mp_verify(payload, solution_data)
                return self._legacy_verify(payload)
            except Exception as e:
                log.debug(f"WAF solve attempt {attempt + 1} failed: {e}")
                self.__class__._cached_key = None
                self.__class__._key_extracted_at = 0.0
                self._ensure_key()
                if attempt == max_retries - 1:
                    raise

    def _mp_verify(self, payload, solution_data):
        self.session.headers.update({
            "origin": f"https://{self.domain}",
            "referer": f"https://{self.domain}/",
        })
        if "content-type" in self.session.headers:
            del self.session.headers["content-type"]

        metadata_json = json.dumps(payload, separators=(',', ':'))
        mp = CurlMime()
        mp.addpart(name="solution_data", content_type="text/plain", data=solution_data.encode('utf-8'))
        mp.addpart(name="solution_metadata", content_type="application/json", data=metadata_json.encode('utf-8'))

        res = self.session.post(f"{self.base_verify_url}/mp_verify", multipart=mp)
        try:
            result = res.json()
        except Exception:
            raise Exception(f"mp_verify returned non-JSON: {res.text[:200]}")

        if result.get("token"):
            return result["token"]
        if result.get("inputs"):
            raise Exception("mp_verify: トークン取得失敗 (新しいチャレンジが要求されました)")
        raise Exception(f"mp_verify: 予期しないレスポンス: {result}")

    def _legacy_verify(self, payload):
        self.session.headers.update({
            "content-type": "text/plain;charset=UTF-8",
            "origin": f"https://{self.domain}",
            "referer": f"https://{self.domain}/",
        })
        res = self.session.post(f"{self.base_verify_url}/verify", json=payload)
        try:
            result = res.json()
        except Exception:
            raise Exception(f"verify returned non-JSON: {res.text[:200]}")
        return result["token"]


def solve_aws_waf_challenge(html: str, user_agent: str, domain: str = "www.paypay.ne.jp") -> str:
    match_props = re.search(r'window\.gokuProps\s*=\s*({.*?});', html, re.DOTALL)
    goku_props = None
    if match_props:
        try:
            goku_props = json.loads(match_props.group(1))
            log.info("gokuProps found in HTML")
        except json.JSONDecodeError as e:
            log.warning(f"Failed to parse gokuProps: {e}")

    match_challenge_url = re.search(r'src=["\'](https://[^"\']+/challenge\.js)', html)
    if not match_challenge_url:
        match_captcha = re.search(r'src=["\']https://([^/]+)/captcha\.js', html)
        if match_captcha:
            raise ValueError(
                "AWS WAF CAPTCHA detected (captcha.js). "
                "This solver only supports challenge.js. "
                "Manual intervention or external CAPTCHA solving is required."
            )
        raise ValueError("challenge.js URL not found in HTML")

    challenge_url = match_challenge_url.group(1)

    if goku_props is None:
        log.warning("gokuProps not found. Proceeding with empty goku_props.")
        goku_props = {}

    solver = AwsWafSolver(goku_props, challenge_url, domain, user_agent)
    return solver.solve()
