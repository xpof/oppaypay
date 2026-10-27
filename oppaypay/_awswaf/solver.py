import re
import json
import random
from curl_cffi import requests, CurlMime
from .verify import CHALLENGE_TYPES, BANDWIDTH_CHALLENGE, get_fp

def solve_aws_waf_challenge(html: str, user_agent: str, domain: str = "www.paypay.ne.jp") -> str:
    match_props = re.search(r'window\.gokuProps\s*=\s*({.*?});', html)
    if not match_props:
        raise ValueError("gokuProps not found in HTML")
    goku_props = json.loads(match_props.group(1))
    
    match_host = re.search(r'src=["\']https://([^/]+)/challenge\.js', html)
    if not match_host:
        match_host = re.search(r'https://([^/]+)/', html)
    if not match_host:
        raise ValueError("WAF endpoint host not found in HTML")
    
    endpoint = match_host.group(1)

    session = requests.Session(impersonate="chrome")
    session.headers = {
        "connection": "keep-alive",
        "sec-ch-ua-platform": "\"Android\"",
        "user-agent": user_agent,
        "sec-ch-ua": "\"Not A(Brand\";v=\"8\", \"Chromium\";v=\"132\", \"Android WebView\";v=\"132\"",
        "sec-ch-ua-mobile": "?1",
        "accept": "*/*",
        "sec-fetch-site": "cross-site",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "ja-JP,ja;q=0.9"
    }

    inputs = session.get(f"https://{endpoint}/inputs?client=browser").json()
    verify_func = CHALLENGE_TYPES.get(inputs["challenge_type"])
    if not verify_func:
        raise ValueError(f"Unknown challenge type: {inputs['challenge_type']}")
        
    checksum, fp = get_fp(user_agent)
    is_mp = (inputs["challenge_type"] == BANDWIDTH_CHALLENGE)

    if is_mp:
        solution_data = verify_func(inputs["challenge"]["input"], checksum, inputs["difficulty"])
        solution_in_metadata = None
    else:
        solution_data = None
        solution_in_metadata = verify_func(inputs["challenge"]["input"], checksum, inputs["difficulty"])

    payload = {
        "challenge": inputs["challenge"],
        "checksum": checksum,
        "solution": solution_in_metadata,
        "signals": [{"name": "Zoey", "value": {"Present": fp}}],
        "existing_token": None,
        "client": "Browser",
        "domain": domain,
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
            {"name": "3", "value": round(random.uniform(8.0, 16.0), 15), "unit": "2"},
            {"name": "7", "value": 0, "unit": "4"},
            {"name": "1", "value": round(random.uniform(50.0, 90.0), 1), "unit": "2"},
            {"name": "4", "value": round(random.uniform(4.0, 8.0), 13), "unit": "2"},
            {"name": "5", "value": round(random.uniform(0.3, 1.5), 13), "unit": "2"},
            {"name": "6", "value": round(random.uniform(60.0, 90.0), 14), "unit": "2"},
            {"name": "8", "value": 1, "unit": "4"},
        ],
        "goku_props": goku_props,
    }

    if is_mp:
        session.headers.update({"origin": f"https://{domain}", "referer": f"https://{domain}/"})
        if "content-type" in session.headers: del session.headers["content-type"]
        
        mp = CurlMime()
        mp.addpart(name="solution_data", content_type="text/plain", data=solution_data.encode('utf-8'))
        mp.addpart(name="solution_metadata", content_type="application/json", data=json.dumps(payload, separators=(',', ':')).encode('utf-8'))
        
        res = session.post(f"https://{endpoint}/mp_verify", multipart=mp)
    else:
        session.headers.update({"content-type": "text/plain;charset=UTF-8", "origin": f"https://{domain}", "referer": f"https://{domain}/"})
        res = session.post(f"https://{endpoint}/verify", json=payload)
        
    result = res.json()
    if result.get("token"):
        return result["token"]
    if result.get("inputs"):
        raise Exception("WAF challenge failed: new challenge returned")
    raise Exception(f"WAF challenge failed: {result}")