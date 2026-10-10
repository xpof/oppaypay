import logging

log = logging.getLogger("oppaypay.fingerprint")

IOS_PROFILES = [
    "safari260_ios",
    "safari184_ios",
    "safari180_ios",
    "safari172_ios",
    "safari170",
    "safari155",
]

GENERIC_PROFILES = [
    "safari_ios",
    "safari",
    "chrome",
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

    for profile in IOS_PROFILES:
        if not available or profile in available:
            log.info(f"fingerprint profile: {profile}")
            return profile

    for profile in GENERIC_PROFILES:
        if not available or profile in available:
            log.info(f"fingerprint fallback profile: {profile}")
            return profile

    log.warning("利用可能なプロファイルが見つかりません。safari を使用します。")
    return "safari"


def ios_27_user_agent() -> str:
    return (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 27_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/27.0 Mobile/15E148 Safari/604.1"
    )


def ios_27_webview_user_agent() -> str:
    return (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 27_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Mobile/15E148 [PayPay]"
    )


def ios_27_portal_headers() -> dict:
    return {
        "sec-ch-ua": '"Safari";v="27", "Not-A.Brand";v="8"',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": '"iOS"',
        "X-Requested-With": "jp.ne.paypay.ios.app",
    }


__all__ = [
    "IOS_PROFILES",
    "GENERIC_PROFILES",
    "select_profile",
    "ios_27_user_agent",
    "ios_27_webview_user_agent",
    "ios_27_portal_headers",
]