import re
import json
import random
import logging
from curl_cffi import requests, CurlMime
from .verify import CHALLENGE_TYPES, BANDWIDTH_CHALLENGE, get_fp
from .crypto import update_key_from_goku_props
from .._fingerprint import select_profile

log = logging.getLogger(__name__)

class AwsWafSolver:
    def __init__(self, goku_props: dict, endpoint: str, domain: str, user_agent: str):
        self.session = requests.Session(impersonate=select_profile(user_agent))
        self.session.headers = {
            "connection": "keep-alive",
            "sec-ch-ua-platform": "\"iOS\"" if "iPhone" in user_agent else "\"Android\"" if "Android" in user_agent else "\"Windows\"",
            "user-agent": user_agent,
            "sec-ch-ua": '"Not/A)Brand";v="99", "Safari";v="26", "WebKit";v="605"' if "iPhone" in user_agent else '"Not A(Brand";v="8", "Chromium";v="132"',
            "sec-ch-ua-mobile": "?1",
            "accept": "*/*",
            "sec-fetch-site": "cross-site",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "ja-JP,ja;q=0.9"
        }
        self.goku_props = goku_props
        self.endpoint = endpoint
        self.domain = domain

    def get_inputs(self):
        return self.session.get(f"https://{self.endpoint}/inputs?client=browser").json()

    def build_payload(self, inputs: dict):
        verify_func = CHALLENGE_TYPES.get(inputs["challenge_type"])
        if not verify_func:
            raise ValueError(f"Unknown challenge type: {inputs['challenge_type']}")
        checksum, fp = get_fp(self.session.headers["user-agent"])
        is_mp = (inputs["challenge_type"] == BANDWIDTH_CHALLENGE)
        if is_mp:
            solution_data = verify_func(inputs["challenge"]["input"], checksum, inputs["difficulty"])
            solution_in_metadata = None
        else:
            solution_data = None
            solution_in_metadata = verify_func(inputs["challenge"]["input"], checksum, inputs["difficulty"])
        payload = {
            "challenge": inputs["challenge"], "checksum": checksum, "solution": solution_in_metadata,
            "signals": [{"name": "Zoey", "value": {"Present": fp}}], "existing_token": None,
            "client": "Browser", "domain": self.domain,
            "metrics": [
                {"name": "2", "value": round(random.uniform(0.5, 3.0), 13), "unit": "2"},
                {"name": "100", "value": 1, "unit": "2"}, {"name": "101", "value": 1, "unit": "2"},
                {"name": "102", "value": 1, "unit": "2"}, {"name": "103", "value": random.randint(8, 12), "unit": "2"},
                {"name": "104", "value": 0, "unit": "2"}, {"name": "105", "value": 0, "unit": "2"},
                {"name": "106", "value": 0, "unit": "2"}, {"name": "107", "value": 0, "unit": "2"},
                {"name": "108", "value": 1, "unit": "2"}, {"name": "undefined", "value": 1, "unit": "2"},
                {"name": "110", "value": 0, "unit": "2"}, {"name": "111", "value": random.randint(20, 35), "unit": "2"},
                {"name": "112", "value": random.randint(1, 3), "unit": "2"}, {"name": "undefined", "value": 1, "unit": "2"},
                {"name": "3", "value": round(random.uniform(8.0, 16.0), 15), "unit": "2"}, {"name": "7", "value": 0, "unit": "4"},
                {"name": "1", "value": round(random.uniform(50.0, 90.0), 1), "unit": "2"},
                {"name": "4", "value": round(random.uniform(4.0, 8.0), 13), "unit": "2"},
                {"name": "5", "value": round(random.uniform(0.3, 1.5), 13), "unit": "2"},
                {"name": "6", "value": round(random.uniform(60.0, 90.0), 14), "unit": "2"}, {"name": "8", "value": 1, "unit": "4"},
            ],
            "goku_props": self.goku_props,
        }
        return payload, solution_data, is_mp

    def solve(self, max_retries=3):
        for attempt in range(max_retries):
            try:
                inputs = self.get_inputs()
                payload, solution_data, is_mp = self.build_payload(inputs)
                if is_mp:
                    return self._mp_verify(payload, solution_data)
                return self._legacy_verify(payload)
            except Exception:
                if attempt == max_retries - 1:
                    raise

    def _mp_verify(self, payload, solution_data):
        self.session.headers.update({"origin": f"https://{self.domain}", "referer": f"https://{self.domain}/"})
        if "content-type" in self.session.headers: del self.session.headers["content-type"]
        metadata_json = json.dumps(payload, separators=(',', ':'))
        mp = CurlMime()
        mp.addpart(name="solution_data", content_type="text/plain", data=solution_data.encode('utf-8'))
        mp.addpart(name="solution_metadata", content_type="application/json", data=metadata_json.encode('utf-8'))
        res = self.session.post(f"https://{self.endpoint}/mp_verify", multipart=mp)
        result = res.json()
        if result.get("token"): return result["token"]
        if result.get("inputs"): raise Exception(f"mp_verify: トークン取得失敗")
        raise Exception(f"mp_verify: 予期しないレスポンス: {result}")

    def _legacy_verify(self, payload):
        self.session.headers.update({"content-type": "text/plain;charset=UTF-8", "origin": f"https://{self.domain}", "referer": f"https://{self.domain}/"})
        res = self.session.post(f"https://{self.endpoint}/verify", json=payload).json()
        return res["token"]

def solve_aws_waf_challenge(html: str, user_agent: str, domain: str = "www.paypay.ne.jp") -> str:

    match_props = re.search(r'window\.gokuProps\s*=\s*({.*?});', html, re.DOTALL)
    goku_props = None
    if match_props:
        try:
            goku_props = json.loads(match_props.group(1))
            log.info("gokuProps found in HTML")
        except json.JSONDecodeError as e:
            log.warning(f"Failed to parse gokuProps: {e}")

    match_host = re.search(r'src=["\']https://([^/]+)/challenge\.js', html)
    if not match_host:
        match_captcha = re.search(r'src=["\']https://([^/]+)/captcha\.js', html)
        if match_captcha:
            raise ValueError(
                "AWS WAF CAPTCHA detected (captcha.js). "
                "This solver only supports challenge.js. "
                "Manual intervention or external CAPTCHA solving is required."
            )
        match_host = re.search(r'https://([^/]+)/', html)
        if not match_host:
            raise ValueError("WAF endpoint host not found in HTML")

    endpoint = match_host.group(1)

    if goku_props is None:
        log.warning("gokuProps not found. Proceeding with empty goku_props.")
        goku_props = {}

    try:
        update_key_from_goku_props(goku_props)
    except Exception as e:
        log.debug(f"Failed to update WAF key: {e}")

    solver = AwsWafSolver(goku_props, endpoint, domain, user_agent)
    return solver.solve()
