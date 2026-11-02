import secrets
import re
import logging
from typing import Optional

log = logging.getLogger(__name__)


_IOS_PROFILES = [
    {"name": "safari_ios", "weight": 40, "min_os": "15.0", "max_os": "99.9"},
    {"name": "safari15_3", "weight": 5, "min_os": "15.0", "max_os": "15.4"},
    {"name": "safari15_5", "weight": 5, "min_os": "15.5", "max_os": "16.9"},
    {"name": "safari17_0", "weight": 10, "min_os": "17.0", "max_os": "17.1"},
    {"name": "safari17_2_ios", "weight": 10, "min_os": "17.2", "max_os": "17.9"},
    {"name": "safari18_0", "weight": 15, "min_os": "18.0", "max_os": "18.1"},
    {"name": "safari18_2", "weight": 15, "min_os": "18.2", "max_os": "99.9"},
]

_ANDROID_PROFILES = [
    {"name": "chrome_android", "weight": 30, "min_os": "10", "max_os": "99"},
    {"name": "chrome99_android", "weight": 2, "min_os": "10", "max_os": "11"},
    {"name": "chrome100_android", "weight": 2, "min_os": "10", "max_os": "11"},
    {"name": "chrome101_android", "weight": 2, "min_os": "10", "max_os": "11"},
    {"name": "chrome104_android", "weight": 3, "min_os": "10", "max_os": "12"},
    {"name": "chrome107_android", "weight": 3, "min_os": "10", "max_os": "12"},
    {"name": "chrome110_android", "weight": 5, "min_os": "11", "max_os": "12"},
    {"name": "chrome116_android", "weight": 5, "min_os": "11", "max_os": "13"},
    {"name": "chrome119_android", "weight": 5, "min_os": "12", "max_os": "13"},
    {"name": "chrome120_android", "weight": 5, "min_os": "12", "max_os": "13"},
    {"name": "chrome123_android", "weight": 8, "min_os": "12", "max_os": "14"},
    {"name": "chrome124_android", "weight": 8, "min_os": "12", "max_os": "14"},
    {"name": "chrome131_android", "weight": 15, "min_os": "13", "max_os": "99"},
]

_DESKTOP_PROFILES = [
    # 汎用名
    {"name": "chrome", "weight": 15},
    {"name": "safari", "weight": 10},
    {"name": "firefox", "weight": 5},
    {"name": "edge", "weight": 5},
    # Chrome バージョン固定
    {"name": "chrome99", "weight": 1},
    {"name": "chrome100", "weight": 1},
    {"name": "chrome101", "weight": 1},
    {"name": "chrome104", "weight": 2},
    {"name": "chrome107", "weight": 2},
    {"name": "chrome110", "weight": 3},
    {"name": "chrome116", "weight": 3},
    {"name": "chrome119", "weight": 3},
    {"name": "chrome120", "weight": 3},
    {"name": "chrome123", "weight": 5},
    {"name": "chrome124", "weight": 5},
    {"name": "chrome131", "weight": 8},
    {"name": "chrome133a", "weight": 8},
    {"name": "chrome136", "weight": 8},
    # Safari (macOS)
    {"name": "safari15_3", "weight": 2},
    {"name": "safari15_5", "weight": 2},
    {"name": "safari17_0", "weight": 3},
    {"name": "safari18_0", "weight": 5},
    # Firefox
    {"name": "firefox109", "weight": 2},
    {"name": "firefox147", "weight": 3},
    # Edge
    {"name": "edge99", "weight": 1},
    {"name": "edge101", "weight": 2},
    {"name": "edge127", "weight": 3},
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

    os_version = _extract_os_version(user_agent, platform)
    candidates = _filter_profiles(profiles, os_version)

    for _ in range(len(candidates)):
        selected = _weighted_choice(candidates)
        if _validate_profile(selected):
            log.debug(f"Selected profile: {selected} (platform={platform}, os={os_version})")
            return selected

    fallback = _FALLBACK.get(platform, "chrome")
    log.warning(f"All candidates failed. Falling back to '{fallback}'.")
    if _validate_profile(fallback):
        return fallback

    log.error("Fallback profile also failed. Forcing 'chrome'.")
    return "chrome"
