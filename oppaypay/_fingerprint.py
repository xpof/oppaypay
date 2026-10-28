import secrets
import re
from typing import Optional


_IOS_PROFILES = [
    {"name": "safari_ios", "weight": 100},
]

_ANDROID_PROFILES = [
    {"name": "chrome131", "weight": 60},
    {"name": "chrome124", "weight": 25},
    {"name": "chrome120", "weight": 15},
]

_DESKTOP_PROFILES = [
    {"name": "chrome131", "weight": 40},
    {"name": "chrome124", "weight": 30},
    {"name": "chrome", "weight": 30},
]

_FALLBACK = {
    "ios": "safari_ios",
    "android": "chrome131",
    "desktop": "chrome131",
}

def _weighted_choice(profiles: list) -> str:
    total = sum(p["weight"] for p in profiles)
    r = secrets.randbelow(total)
    cumulative = 0
    for p in profiles:
        cumulative += p["weight"]
        if r < cumulative:
            return p["name"]
    return profiles[-1]["name"]

def _detect_platform(user_agent: Optional[str]) -> str:
    if not user_agent:
        return "ios"
    ua_lower = user_agent.lower()
    if "iphone" in ua_lower or "ipad" in ua_lower or "mac os x" in ua_lower:
        return "ios"
    if "android" in ua_lower:
        return "android"
    return "desktop"

def _extract_os_version(user_agent: Optional[str], platform: str) -> Optional[str]:
    if not user_agent:
        return None
    if platform == "ios":
        match = re.search(r"OS (\d+)_(\d+)", user_agent)
        if match:
            return f"{match.group(1).zfill(2)}.{match.group(2).zfill(2)}"
    if platform == "android":
        match = re.search(r"Android (\d+)", user_agent)
        if match:
            return match.group(1).zfill(2)
    return None

def _validate_profile(profile_name: str) -> bool:
    try:
        from curl_cffi import requests as curl_requests
        s = curl_requests.Session(impersonate=profile_name)
        del s
        return True
    except Exception:
        return False

def select_profile(user_agent: Optional[str] = None) -> str:
    platform = _detect_platform(user_agent)
    
    if platform == "ios":
        profiles = _IOS_PROFILES
    elif platform == "android":
        profiles = _ANDROID_PROFILES
    else:
        profiles = _DESKTOP_PROFILES
    
    selected = _weighted_choice(profiles)
    
    if not _validate_profile(selected):
        selected = _FALLBACK[platform]
        if not _validate_profile(selected):
            selected = "chrome131"
    
    return selected
