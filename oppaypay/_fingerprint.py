import logging

log = logging.getLogger("oppaypay.fingerprint")

ANDROID_PROFILES = [
    "chrome124",
    "chrome120",
    "chrome116",
    "chrome110",
    "chrome",
]

GENERIC_PROFILES = [
    "safari",
    "edge101",
]

def _available_profiles() -> set:
    try:
        from curl_cffi.requests import BrowserType
        available = set()
        for attr in dir(BrowserType):
            if not attr.startswith("_"):
                available.add(getattr(BrowserType, attr))
        return available
    except Exception as e:
        log.warning(f"BrowserType の取得に失敗: {e}")
        return set()

def select_profile() -> str:
    available = _available_profiles()
    for profile in ANDROID_PROFILES:
        if not available or profile in available:
            log.info(f"fingerprint profile: {profile}")
            return profile
    for profile in GENERIC_PROFILES:
        if not available or profile in available:
            log.info(f"fingerprint fallback profile: {profile}")
            return profile
    log.warning("利用可能なプロファイルが見つかりません。chrome を使用します。")
    return "chrome"

def android_17_user_agent() -> str:
    return (
        "Mozilla/5.0 (Linux; Android 17; SC-53F) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Mobile Safari/537.36"
    )

def android_17_webview_user_agent() -> str:
    return (
        "Mozilla/5.0 (Linux; Android 17; SC-53F Build/UP1A.231005.007; wv) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Version/4.0 Chrome/124.0.0.0 Mobile Safari/537.36 [PayPay]"
    )

def android_17_portal_headers() -> dict:
    return {
        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": '"Android"',
        "X-Requested-With": "jp.ne.paypay.android.app",
    }

__all__ = [
    "ANDROID_PROFILES",
    "GENERIC_PROFILES",
    "select_profile",
    "android_17_user_agent",
    "android_17_webview_user_agent",
    "android_17_portal_headers",
]