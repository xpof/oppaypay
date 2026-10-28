import secrets
import re
from typing import Optional
import logging

log = logging.getLogger(__name__)

# ============================================================
# curl_cffi のバージョンに依存しないよう、汎用名（エイリアス）を使用。
# 特定のバージョン名（safari_ios_18_0 等）は廃止されることがあるため、
# 原則として "safari_ios", "chrome", "chrome_android" などの
# 広くサポートされている名前を優先する。
# ============================================================

_IOS_PROFILES = [
    {"name": "safari_ios", "weight": 100, "min_os": "15.0", "max_os": "99.9"},
]

_ANDROID_PROFILES = [
    {"name": "chrome_android", "weight": 50, "min_os": "10", "max_os": "99"},
    {"name": "chrome131", "weight": 30, "min_os": "12", "max_os": "99"},
    {"name": "chrome124", "weight": 20, "min_os": "11", "max_os": "99"},
]

_DESKTOP_PROFILES = [
    {"name": "chrome", "weight": 40},
    {"name": "safari", "weight": 30},
    {"name": "chrome131", "weight": 30},
]

_FALLBACK = {
    "ios": "safari_ios",
    "android": "chrome_android",
    "desktop": "chrome"
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
        if p.get("min_os") and os_version < p["min_os"]: 
            continue
        if p.get("max_os") and os_version > p["max_os"]: 
            continue
        filtered.append(p)
    return filtered or profiles

def _validate_profile(profile_name: str) -> bool:
    """指定されたプロファイル名が現在の curl_cffi でサポートされているか検証"""
    try:
        from curl_cffi import requests as curl_requests
        s = curl_requests.Session(impersonate=profile_name)
        del s
        return True
    except Exception as e:
        log.debug(f"Profile validation failed for '{profile_name}': {e}")
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
        log.warning(f"Selected profile '{selected}' not supported. Falling back...")
        
        for p in candidates:
            if _validate_profile(p["name"]):
                selected = p["name"]
                log.info(f"Using alternative profile: {selected}")
                break
        else:
            selected = _FALLBACK.get(platform, "chrome")
            log.warning(f"All candidates failed. Using fallback: {selected}")
            
            if not _validate_profile(selected):
                log.error(f"Fallback profile '{selected}' also failed. Forcing 'chrome'.")
                selected = "chrome"

    return selected
