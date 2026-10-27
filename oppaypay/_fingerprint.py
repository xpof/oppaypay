import secrets
import re
from typing import Optional

_IOS_PROFILES = [
    {"name": "safari_ios_17_0", "weight": 10, "min_os": "17.0", "max_os": "17.1"},
    {"name": "safari_ios_17_2", "weight": 25, "min_os": "17.2", "max_os": "17.9"},
    {"name": "safari_ios_18_0", "weight": 40, "min_os": "18.0", "max_os": "25.9"},
    {"name": "safari_ios_18_0", "weight": 25, "min_os": "26.0", "max_os": "99.9"},
]

_ANDROID_PROFILES = [
    {"name": "chrome120", "weight": 15, "min_os": "10", "max_os": "13"},
    {"name": "chrome123", "weight": 25, "min_os": "10", "max_os": "14"},
    {"name": "chrome124", "weight": 25, "min_os": "11", "max_os": "14"},
    {"name": "chrome131", "weight": 35, "min_os": "12", "max_os": "15"},
]

_DESKTOP_PROFILES = [
    {"name": "chrome131", "weight": 30},
    {"name": "chrome133", "weight": 30},
    {"name": "safari_17_0", "weight": 20},
    {"name": "safari_18_0", "weight": 20},
]

_FALLBACK = {
    "ios": "safari_ios_18_0",
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

def _filter_profiles(profiles: list, os_version: Optional[str]) -> list:
    if not os_version:
        return profiles
    filtered = []
    for p in profiles:
        min_os = p.get("min_os")
        max_os = p.get("max_os")
        if min_os and os_version < min_os:
            continue
        if max_os and os_version > max_os:
            continue
        filtered.append(p)
    return filtered or profiles

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
    os_version = _extract_os_version(user_agent, platform)
    candidates = _filter_profiles(profiles, os_version)
    selected = _weighted_choice(candidates)
    if not _validate_profile(selected):
        selected = _FALLBACK[platform]
        if not _validate_profile(selected):
            selected = "chrome131"
    return selected