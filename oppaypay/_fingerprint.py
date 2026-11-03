import secrets
import re
import logging
from typing import Optional

log = logging.getLogger(__name__)



_IOS_PROFILES = [
    {"name": "safari_ios", "weight": 100},
]

_ANDROID_PROFILES = [
    {"name": "chrome_android", "weight": 100},
]

_DESKTOP_PROFILES = [
    {"name": "chrome", "weight": 60},
    {"name": "safari", "weight": 40},
]

_FALLBACK = {
    "ios": "safari_ios",
    "android": "chrome_android",
    "desktop": "chrome",
}

def _weighted_choice(profiles: list) -> str:
    total = sum(p["weight"] for p in profiles)
    if total == 0:
        return profiles[0]["name"]
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

_validated_profiles: dict[str, bool] = {}

def _validate_profile(profile_name: str) -> bool:
    if profile_name in _validated_profiles:
        return _validated_profiles[profile_name]
    try:
        from curl_cffi import requests as curl_requests
        s = curl_requests.Session(impersonate=profile_name)
        del s
        _validated_profiles[profile_name] = True
        return True
    except Exception as e:
        log.debug(f"Profile validation failed for '{profile_name}': {e}")
        _validated_profiles[profile_name] = False
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
    if _validate_profile(selected):
        return selected

    fallback = _FALLBACK.get(platform, "chrome")
    if _validate_profile(fallback):
        return fallback

    return "chrome"
