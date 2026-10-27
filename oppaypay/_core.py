import random
import time
import logging
import secrets
import hashlib
from typing import NamedTuple
from uuid import uuid4
from curl_cffi import requests as curl_requests
import pkce
from ._fingerprint import select_profile
from ._sensors import generate_device_state, update_header_device_state
from ._awswaf import solve_aws_waf_challenge
from .exceptions import (
    OpPayPayError, OpPayPayLoginError, OpPayPayNetworkError,
    OpPayPayBotDetectedError, OpPayPayEKYCRequiredError,
    OpPayPayAccountLockedError, OpPayPayRateLimitError,
)

log = logging.getLogger("oppaypay.core")

VERSION = "5.57.0"
BASE_URL = "https://app4.paypay.ne.jp"
PORTAL_URL = "https://www.paypay.ne.jp"

class Balance(NamedTuple):
    money: int | None
    money_light: int
    all_balance: int
    useable_balance: int
    points: int
    raw: dict

class PayPayCore:
    def __init__(self, phone: str | None = None, password: str | None = None,
                 device_uuid: str | None = None, client_uuid: str | None = None,
                 access_token: str | None = None, refresh_token: str | None = None, 
                 proxy: str | None = None, humanize: bool = True):
        if phone and "-" in phone:
            phone = phone.replace("-", "")
        
        self.phone = phone
        self.password = password
        self.registered_device = device_uuid is not None
        self.device_uuid = device_uuid or str(uuid4())
        self.client_uuid = client_uuid or str(uuid4())
        self.refresh_token = refresh_token
        self.humanize = humanize
        
        self._mental_focus = secrets.randbelow(1000) / 1000.0
        self._login_headers: dict = {}

        self.session = curl_requests.Session(
            impersonate="safari_ios_17_0",
            proxies={"http": proxy, "https": proxy} if proxy else None,
            timeout=30,
        )
        
        self.access_token: str | None = None
        self.code_verifier = None
        
        device_state = generate_device_state()
        self.session.headers = {
            "Accept": "*/*",
            "Accept-Charset": "UTF-8",
            "Accept-Encoding": "gzip",
            "Client-Mode": "NORMAL",
            "Client-OS-Release-Version": "26",
            "Client-OS-Type": "IOS",
            "Client-OS-Version": "26.6",
            "Client-Type": "PAYPAYAPP",
            "Client-UUID": self.client_uuid,
            "Client-Version": VERSION,
            "Connection": "Keep-Alive",
            "Content-Type": "application/x-www-form-urlencoded",
            "Device-Acceleration": device_state.device_acceleration,
            "Device-Acceleration-2": device_state.device_acceleration_2,
            "Device-Brand-Name": "Apple",
            "Device-Hardware-Name": "iPhone",
            "Device-In-Call": "false",
            "Device-Lock-App-Setting": "false",
            "Device-Lock-Type": "NONE",
            "Device-Manufacturer-Name": "Apple",
            "Device-Name": "iPhone 17e",
            "Device-Orientation": device_state.device_orientation,
            "Device-Orientation-2": device_state.device_orientation_2,
            "Device-Rotation": device_state.device_rotation,
            "Device-Rotation-2": device_state.device_rotation_2,
            "Device-UUID": self.device_uuid,
            "Host": "app4.paypay.ne.jp",
            "Is-Emulator": "false",
            "Network-Status": "WIFI",
            "System-Locale": "ja",
            "Timezone": "Asia/Tokyo",
            "User-Agent": f"PaypayApp/{VERSION} iPhone17e"
        }
        
        if access_token:
            self.access_token = access_token
            self.session.headers["Authorization"] = f"Bearer {self.access_token}"
            self.session.headers["content-type"] = "application/json"

    def _human_delay(self, url: str = ""):
        if not self.humanize:
            return
        
        drift = (secrets.randbelow(200) / 100.0) - 1.0
        volatility = secrets.randbelow(50) / 100.0
        self._mental_focus += drift * volatility
        
        upper_bound = 0.8 + (secrets.randbelow(20) / 100.0)
        self._mental_focus = max(0.0, min(self._mental_focus, upper_bound))
        
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        url_entropy = int(url_hash[:8], 16) / (2**32)
        
        base_delay = secrets.randbelow(1000) / 1000.0
        focus_multiplier = 1.0 + (1.0 - self._mental_focus)
        entropy_multiplier = 1.0 + url_entropy
        
        delay = base_delay * focus_multiplier * entropy_multiplier
        
        max_limit = 3.0 + (secrets.randbelow(500) / 100.0)
        delay = min(delay, max_limit)
        
        min_limit = secrets.randbelow(50) / 1000.0
        delay = max(delay, min_limit)
        
        time.sleep(delay)

    def request(self, method: str, url: str, **kwargs):
        self._human_delay(url)
        
        if method.lower() == "get":
            response = self.session.get(url, **kwargs)
        elif method.lower() == "post":
            response = self.session.post(url, **kwargs)
        else:
            raise ValueError("Invalid HTTP method.")
        
        try:
            response_json = response.json()
        except Exception:
            raise OpPayPayNetworkError(f"Failed to parse JSON response: {response.text}")
        
        header = response_json.get("header", {})
        if header:
            result_code = header.get("resultCode")
            if result_code == "S0001":
                raise OpPayPayBotDetectedError("Bot検知によりログアウトされました。")
            elif result_code == "S4002":
                pass
            elif result_code != "S0000":
                try:
                    if response_json["error"]["displayErrorResponse"]["description"] == "しばらく時間をおいて、再度お試しください":
                        raise OpPayPayRateLimitError("レート制限に達しました")
                except KeyError:
                    pass
                raise OpPayPayError(response_json)
        
        return response_json

    def _web_request(self, method: str, url: str, headers: dict, **kwargs):
        self._human_delay(url)
        
        if method.lower() == "get":
            response = self.session.get(url, headers=headers, **kwargs)
        elif method.lower() == "post":
            response = self.session.post(url, headers=headers, **kwargs)
        else:
            raise ValueError("Invalid HTTP method.")
        
        if response.status_code == 202 and 'x-amzn-waf-action' in response.headers:
            user_agent = headers.get("User-Agent", "")
            aws_waf_token = solve_aws_waf_challenge(response.text, user_agent)
            self.session.cookies.set("aws-waf-token", aws_waf_token, domain=".paypay.ne.jp")
            
            self._human_delay(url)
            if method.lower() == "get":
                response = self.session.get(url, headers=headers, **kwargs)
            else:
                response = self.session.post(url, headers=headers, **kwargs)
        
        return response

    def login_start(self):
        if not self.phone:
            raise OpPayPayLoginError("電話番号を入力してください")
        
        self.access_token = None
        self.code_verifier, self.code_challenge = pkce.generate_pkce_pair(43)
        
        payload = {
            "clientId": "pay2-mobile-app-client",
            "clientAppVersion": VERSION,
            "clientOsVersion": "26.6",
            "clientOsType": "IOS",
            "redirectUri": "paypay://oauth2/callback",
            "responseType": "code",
            "state": pkce.generate_code_verifier(43),
            "codeChallenge": self.code_challenge,
            "codeChallengeMethod": "S256",
            "scope": "REGULAR",
            "tokenVersion": "v2",
            "prompt": "",
            "uiLocales": "ja"
        }
        
        response = self.request("post", f"{BASE_URL}/bff/v2/oauth2/par?payPayLang=ja", data=payload)
        if response["header"]["resultCode"] != "S0000":
            raise OpPayPayLoginError(response)
        
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "ja-JP,ja;q=0.9",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Host": "www.paypay.ne.jp",
            "is-emulator": "false",
            "Pragma": "no-cache",
            "sec-ch-ua": '"Not/A)Brand";v="99", "Safari";v="26", "WebKit";v="605"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"iOS"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 26_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/23G71",
            "X-Requested-With": "jp.ne.paypay.app"
        }
        
        params = {"client_id": "pay2-mobile-app-client", "request_uri": response["payload"]["requestUri"]}
        
        self._web_request("get", f"{PORTAL_URL}/portal/api/v2/oauth2/authorize", headers=headers, params=params, allow_redirects=False)
        
        params = {"client_id": "pay2-mobile-app-client", "mode": "landing"}
        signin_page_response = self._web_request("get", f"{PORTAL_URL}/portal/oauth2/sign-in", headers=headers, params=params)
        
        if signin_page_response.status_code > 400:
            raise OpPayPayLoginError("サインインページの取得に失敗しました")
        
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "ja-JP,ja;q=0.9",
            "Cache-Control": "no-cache",
            "Client-Id": "pay2-mobile-app-client",
            "Client-Type": "PAYPAYAPP",
            "Connection": "keep-alive",
            "Host": "www.paypay.ne.jp",
            "Pragma": "no-cache",
            "Referer": f"{PORTAL_URL}/portal/oauth2/sign-in?client_id=pay2-mobile-app-client&mode=landing",
            "sec-ch-ua": '"Not/A)Brand";v="99", "Safari";v="26", "WebKit";v="605"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"iOS"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 26_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/23G71",
            "X-Requested-With": "jp.ne.paypay.app"
        }
        
        response = self._web_request("get", f"{PORTAL_URL}/portal/api/v2/oauth2/par/check", headers=headers)
        par_check = response.json()
        if par_check["header"]["resultCode"] != "S0000":
            raise OpPayPayLoginError(par_check)
        
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "ja-JP,ja;q=0.9",
            "Cache-Control": "no-cache",
            "Client-Id": "pay2-mobile-app-client",
            "Client-OS-Type": "IOS",
            "Client-OS-Version": "26.6",
            "Client-Type": "PAYPAYAPP",
            "Client-Version": VERSION,
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "Host": "www.paypay.ne.jp",
            "Origin": PORTAL_URL,
            "Pragma": "no-cache",
            "Referer": f"{PORTAL_URL}/portal/oauth2/sign-in?client_id=pay2-mobile-app-client&mode=landing",
            "sec-ch-ua": '"Not/A)Brand";v="99", "Safari";v="26", "WebKit";v="605"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"iOS"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 26_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/23G71",
            "X-Requested-With": "jp.ne.paypay.app"
        }
        
        payload = {"username": self.phone, "password": self.password, "signInAttemptCount": 1}
        response = self._web_request("post", f"{PORTAL_URL}/portal/api/v2/oauth2/sign-in/password", headers=headers, json=payload)
        signin = response.json()
        if signin["header"]["resultCode"] != "S0000":
            raise OpPayPayLoginError(signin)
        
        if self.registered_device:
            try:
                uri = signin["payload"]["redirectUrl"].replace("paypay://oauth2/callback?", "").split("&")
            except Exception:
                raise OpPayPayLoginError("登録されていないDevice-UUID")
            self._finish_token_exchange(uri[0].replace("code=", ""))
        else:
            response = self._web_request("post", f"{PORTAL_URL}/portal/api/v2/oauth2/extension/code-grant/update", headers=headers, json={})
            if response.json()["header"]["resultCode"] != "S0000":
                raise OpPayPayLoginError(response.json())
            
            headers["Referer"] = f"{PORTAL_URL}/portal/oauth2/verification-method?client_id=pay2-mobile-app-client&mode=navigation-2fa"
            payload = {"params": {"extension_id": "user-main-2fa-v1", "data": {"type": "SELECT_FLOW", "payload": {"flow": "OTL", "sign_in_method": "MOBILE", "base_url": f"{PORTAL_URL}/portal/oauth2/l"}}}}
            response = self._web_request("post", f"{PORTAL_URL}/portal/api/v2/oauth2/extension/code-grant/update", headers=headers, json=payload)
            if response.json()["header"]["resultCode"] != "S0000":
                raise OpPayPayLoginError(response.json())
            
            headers["Referer"] = f"{PORTAL_URL}/portal/oauth2/otl-request?client_id=pay2-mobile-app-client&mode=navigation-2fa"
            response = self._web_request("post", f"{PORTAL_URL}/portal/api/v2/oauth2/extension/code-grant/side-channel/next-action-polling", headers=headers, json={"waitUntil": "PT5S"})
            if response.json()["header"]["resultCode"] != "S0000":
                raise OpPayPayLoginError(response.json())
        
        self._login_headers = headers

    def login_confirm(self, url: str):
        if self.session.headers.get("Authorization"):
            return "already logged in"
        
        if "https://" in url:
            url = url.replace(f"{PORTAL_URL}/portal/oauth2/l?id=", "")
        
        headers = self._login_headers.copy()
        headers["Referer"] = f"{PORTAL_URL}/portal/oauth2/l?id={url}&client_id=pay2-mobile-app-client"
        
        response = self._web_request("post", f"{PORTAL_URL}/portal/api/v2/oauth2/extension/sign-in/2fa/otl/verify", headers=headers, json={"code": url})
        if response.json()["header"]["resultCode"] != "S0000":
            raise OpPayPayLoginError(response.json())
        
        payload = {"params": {"extension_id": "user-main-2fa-v1", "data": {"type": "COMPLETE_OTL", "payload": None}}}
        response = self._web_request("post", f"{PORTAL_URL}/portal/api/v2/oauth2/extension/code-grant/update", headers=headers, json=payload)
        get_uri = response.json()
        if get_uri["header"]["resultCode"] != "S0000":
            raise OpPayPayLoginError(get_uri)
        
        try:
            uri = get_uri["payload"]["redirect_uri"].replace("paypay://oauth2/callback?", "").split("&")
        except Exception:
            raise OpPayPayLoginError('redirect_uriが見つかりませんでした\n' + str(get_uri))
        
        self._finish_token_exchange(uri[0].replace("code=", ""))

    def _finish_token_exchange(self, code: str):
        headers = self.session.headers.copy()
        if "Device-Lock-Type" in headers: del headers["Device-Lock-Type"]
        if "Device-Lock-App-Setting" in headers: del headers["Device-Lock-App-Setting"]
        
        confirm_data = {
            "clientId": "pay2-mobile-app-client",
            "redirectUri": "paypay://oauth2/callback",
            "code": code,
            "codeVerifier": self.code_verifier
        }
        
        get_token = self.request("post", f"{BASE_URL}/bff/v2/oauth2/token", headers=headers, data=confirm_data, params={"payPayLang": "ja"})
        if get_token["header"]["resultCode"] != "S0000":
            raise OpPayPayLoginError(get_token)
        
        self.access_token = get_token["payload"]["accessToken"]
        self.refresh_token = get_token["payload"].get("refreshToken")
        self.session.headers["Authorization"] = f"Bearer {self.access_token}"
        self.session.headers["content-type"] = "application/json"
        self.session.headers = update_header_device_state(self.session.headers)

    def refresh_session(self) -> bool:
        if not getattr(self, "refresh_token", None):
            raise OpPayPayLoginError("refresh_token が存在しません。再度ログインしてください。")
        
        headers = self.session.headers.copy()
        if "Device-Lock-Type" in headers: del headers["Device-Lock-Type"]
        if "Device-Lock-App-Setting" in headers: del headers["Device-Lock-App-Setting"]
        
        refresh_data = {
            "clientId": "pay2-mobile-app-client",
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }
        
        get_token = self.request("post", f"{BASE_URL}/bff/v2/oauth2/token", headers=headers, data=refresh_data, params={"payPayLang": "ja"})
        if get_token["header"]["resultCode"] != "S0000":
            raise OpPayPayLoginError(f"トークン更新に失敗しました: {get_token}")
        
        self.access_token = get_token["payload"]["accessToken"]
        self.refresh_token = get_token["payload"].get("refreshToken", self.refresh_token)
        self.session.headers["Authorization"] = f"Bearer {self.access_token}"
        self.session.headers["content-type"] = "application/json"
        self.session.headers = update_header_device_state(self.session.headers)
        return True

    def alive(self) -> bool:
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        
        params = {"payPayLang": "ja"}
        self.request("get", f"{BASE_URL}/bff/v1/getGlobalServiceStatus", params=params)
        self.request("post", f"{BASE_URL}/bff/v4/getHomeDisplayInfo", params=params, json={
            "abTestFlags": {"dedupeFeatureAndFavoritesTab": False},
            "excludeMissionBannerInfoFlag": False,
            "excludeTobaccoPolicyBannerFlag": True,
            "includeBeginnerFlag": False,
            "includeSkinInfoFlag": False,
            "networkStatus": "WIFI"
        })
        self.request("post", f"{BASE_URL}/bff/v1/getFeatureFlagInfo", params=params, json={
            "flagNames": ["enable_home_screen_favoriting_suggestions", "home_screen_all_entry_point_ab_test"]
        })
        return True

    def get_balance(self) -> Balance:
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        
        params = {
            "includePendingBonusLite": "false", "includePending": "true", "noCache": "true",
            "includeKycInfo": "true", "includePayPaySecuritiesInfo": "true",
            "includePointInvestmentInfo": "true", "includePayPayBankInfo": "true",
            "includeGiftVoucherInfo": "true", "payPayLang": "ja"
        }
        
        response = self.request("get", f"{BASE_URL}/bff/v1/getBalanceInfo", params=params)
        try: 
            money = response["payload"]["walletDetail"]["emoneyBalanceInfo"]["balance"]
        except Exception: 
            money = None
        
        return Balance(
            money=money,
            money_light=response["payload"]["walletDetail"]["prepaidBalanceInfo"]["balance"],
            all_balance=response["payload"]["walletSummary"]["allTotalBalanceInfo"]["balance"],
            useable_balance=response["payload"]["walletSummary"]["usableBalanceInfoWithoutCashback"]["balance"],
            points=response["payload"]["walletDetail"]["cashBackBalanceInfo"]["balance"],
            raw=response
        )

    def create_p2pcode(self, amount: int = None):
        if not self.access_token: 
            raise OpPayPayLoginError("まずはログインしてください")
        
        payload = {"amount": None, "sessionId": None}
        if amount:
            payload["amount"] = amount
            payload["sessionId"] = str(uuid4())
        
        return self.request("post", f"{BASE_URL}/bff/v1/createP2PCode", json=payload, params={"payPayLang": "ja"})

    def get_barcode_info(self, url: str):
        if not self.access_token: 
            raise OpPayPayLoginError("まずはログインしてください")
        
        if "https://qr.paypay.ne.jp/" in url: 
            url = url.replace("https://qr.paypay.ne.jp/", "")
        
        return self.request("get", f"{BASE_URL}/bff/v2/getBarcodeInfo?code=https://qr.paypay.ne.jp/{url}", params={"payPayLang": "ja", "isScannedFromFile": "false"})

    def set_money_priority(self, paypay_money: bool = False):
        if not self.access_token: 
            raise OpPayPayLoginError("まずはログインしてください")
        
        payload = {"moneyPriority": "MONEY_FIRST" if paypay_money else "MONEY_LITE_FIRST"}
        return self.request("post", f"{BASE_URL}/p2p/v1/setMoneyPriority", json=payload, params={"payPayLang": "ja"})

    def pay_qr_code(self, url: str):
        if not self.access_token: 
            raise OpPayPayLoginError("まずはログインしてください")
        
        if "https://qr.paypay.ne.jp/" in url: 
            url = url.replace("https://qr.paypay.ne.jp/", "")
        
        barcode_info = self.get_barcode_info(url)
        dynamic = barcode_info["payload"]["codeInfo"]["dynamicCodeInfo"]
        
        payload = {
            "requestId": str(uuid4()),
            "merchantId": dynamic["merchantInfo"]["merchantId"],
            "storeId": "", 
            "stickerId": "",
            "amount": dynamic["amount"],
            "currency": "JPY",
            "paymentMethodId": barcode_info["payload"]["paymentMethodInfo"]["paymentMethodIdString"],
            "paymentMethodType": "WALLET",
            "agreeSimilarTransactionFlag": False,
            "code": dynamic["code"],
            "merchantOrderId": dynamic["merchantOrderId"],
            "mode": "DYNAMIC_QR"
        }
        
        return self.request("post", f"{BASE_URL}/bff/v2/executePayment", json=payload, params={"payPayLang": "ja"})
