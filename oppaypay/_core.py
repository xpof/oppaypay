import random
import time
from typing import NamedTuple
from uuid import uuid4

from curl_cffi import requests as curl_requests

from ._fingerprint import (
    select_profile,
    ios_27_user_agent,
    ios_27_webview_user_agent,
    ios_27_portal_headers,
)
from ._sensors import device_state, motion_payload
from .exceptions import (
    OpPayPayError,
    OpPayPayLoginError,
    OpPayPayNetworkError,
    OpPayPayBotDetectedError,
    OpPayPayEKYCRequiredError,
    OpPayPayAccountLockedError,
    OpPayPayRateLimitError,
)

VERSION = "5.57.0"
BASE_URL = "https://app4.paypay.ne.jp"
PORTAL_URL = "https://www.paypay.ne.jp"

DEVICE = {
    "model": "iPhone 17 Pro",
    "model_id": "iPhone18,1",
    "os": "iOS",
    "os_version": "27.0",
    "app_version": VERSION,
    "build": "27A341",
    "locale": "ja",
    "timezone": "Asia/Tokyo",
    "carrier": "KDDI",
    "screen": "1206x2622",
    "scale": "3.0",
}


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
                 access_token: str | None = None, proxy: str | None = None):
        if phone and "-" in phone:
            phone = phone.replace("-", "")
        self.phone = phone
        self.password = password

        self.registered_device = device_uuid is not None
        self.device_uuid = device_uuid or str(uuid4())
        self.client_uuid = client_uuid or str(uuid4())

        self.impersonate_profile = select_profile()
        proxies = {"http": proxy, "https": proxy} if proxy else None
        self.session = curl_requests.Session(
            impersonate=self.impersonate_profile,
            proxies=proxies,
            timeout=30,
        )

        self.access_token: str | None = None
        self.refresh_token: str | None = None

        self._build_headers()
        if access_token:
            self.access_token = access_token
            self.session.headers["Authorization"] = f"Bearer {access_token}"
            self.session.headers["Content-Type"] = "application/json"

        self._warmup_done = False

    def _build_headers(self):
        h = {
            "Accept": "*/*",
            "Accept-Charset": "UTF-8",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "ja-JP,ja;q=0.9",
            "Client-Mode": "NORMAL",
            "Client-OS-Release-Version": DEVICE["os_version"],
            "Client-OS-Type": "IOS",
            "Client-OS-Version": DEVICE["os_version"],
            "Client-Type": "PAYPAYAPP",
            "Client-UUID": self.client_uuid,
            "Client-Version": VERSION,
            "Connection": "Keep-Alive",
            "Content-Type": "application/x-www-form-urlencoded",
            "Device-Brand-Name": DEVICE["carrier"],
            "Device-Hardware-Name": "arm64",
            "Device-In-Call": "false",
            "Device-Lock-App-Setting": "false",
            "Device-Lock-Type": "NONE",
            "Device-Manufacturer-Name": "Apple",
            "Device-Name": DEVICE["model"],
            "Device-UUID": self.device_uuid,
            "Host": "app4.paypay.ne.jp",
            "Is-Emulator": "false",
            "Network-Status": "WIFI",
            "System-Locale": DEVICE["locale"],
            "Timezone": DEVICE["timezone"],
            "User-Agent": ios_27_user_agent(),
        }
        h.update(device_state())
        self.session.headers = h

    def warmup(self):
        if self._warmup_done:
            return
        try:
            self.session.get(
                f"{PORTAL_URL}/",
                headers=dict(self.session.headers),
            )
            self._warmup_done = True
        except Exception:
            pass

    def request(self, method: str, url: str, **kwargs) -> dict:
        if not self._warmup_done:
            self.warmup()

        time.sleep(random.uniform(0.1, 0.8))

        if method.lower() == "get":
            response = self.session.get(url, **kwargs)
        elif method.lower() == "post":
            response = self.session.post(url, **kwargs)
        else:
            raise ValueError("GET または POST のみ対応しています")

        if response.status_code == 401:
            raise OpPayPayBotDetectedError(
                "Bot検知によりログアウトされました。セッションを再取得してください。"
            )
        if response.status_code == 403:
            raise OpPayPayAccountLockedError(
                f"アクセス拒否（アカウントロックの可能性）: {response.text[:200]}"
            )
        if response.status_code == 428:
            raise OpPayPayEKYCRequiredError(
                "eKYC（本人確認）が完了していません。PayPay公式アプリで完了してください。"
            )
        if response.status_code == 429:
            raise OpPayPayRateLimitError("レート制限に達しました")

        try:
            response_json = response.json()
        except Exception:
            raise OpPayPayNetworkError(f"JSON のパースに失敗しました: {response.text[:200]}")

        header = response_json.get("header", {})
        if header:
            code = header.get("resultCode")
            if code == "S0001":
                raise OpPayPayBotDetectedError(
                    f"アクセストークンが無効です: {header.get('resultMessage')}"
                )
            elif code == "S0002":
                raise OpPayPayBotDetectedError(
                    f"Bot検知: {header.get('resultMessage')}"
                )
            elif code in ("S0000", "S4002"):
                pass
            else:
                try:
                    if response_json["error"]["displayErrorResponse"]["description"] == "しばらく時間をおいて、再度お試しください":
                        raise OpPayPayRateLimitError("レート制限に達しました")
                except KeyError:
                    pass
                raise OpPayPayError(f"{code}: {header.get('resultMessage')}")
        return response_json

    def _require_token(self):
        if not self.access_token:
            raise OpPayPayLoginError("先にログインしてください")

    def login_start(self) -> None:
        import pkce

        self.access_token = None
        self.refresh_token = None
        self.code_verifier, code_challenge = pkce.generate_pkce_pair(43)

        payload = {
            "clientId": "pay2-mobile-app-client",
            "clientAppVersion": VERSION,
            "clientOsVersion": DEVICE["os_version"],
            "clientOsType": "IOS",
            "redirectUri": "paypay://oauth2/callback",
            "responseType": "code",
            "state": pkce.generate_code_verifier(43),
            "codeChallenge": code_challenge,
            "codeChallengeMethod": "S256",
            "scope": "REGULAR",
            "tokenVersion": "v2",
            "prompt": "",
            "uiLocales": "ja",
        }
        response = self.request("post", f"{BASE_URL}/bff/v2/oauth2/par?payPayLang=ja", data=payload)
        if response["header"]["resultCode"] != "S0000":
            raise OpPayPayLoginError(f"PAR リクエストに失敗しました: {response}")

        web_headers = self._portal_headers()

        response = self.session.get(
            f"{PORTAL_URL}/portal/api/v2/oauth2/authorize",
            headers=web_headers,
            params={"client_id": "pay2-mobile-app-client", "request_uri": response["payload"]["requestUri"]},
            allow_redirects=False,
        )

        response = self.session.get(
            f"{PORTAL_URL}/portal/oauth2/sign-in",
            headers=web_headers,
            params={"client_id": "pay2-mobile-app-client", "mode": "landing"},
        )
        if response.status_code > 400:
            raise OpPayPayLoginError("サインインページの取得に失敗しました")

        par_check = self.session.get(f"{PORTAL_URL}/portal/api/v2/oauth2/par/check", headers=web_headers).json()
        if par_check["header"]["resultCode"] != "S0000":
            raise OpPayPayLoginError(par_check)

        signin_headers = self._portal_headers(json_body=True)
        signin = self.session.post(
            f"{PORTAL_URL}/portal/api/v2/oauth2/sign-in/password",
            headers=signin_headers,
            json={"username": self.phone, "password": self.password, "signInAttemptCount": 1},
        ).json()
        if signin["header"]["resultCode"] != "S0000":
            raise OpPayPayLoginError(signin)

        if self.registered_device:
            self._finish_token_exchange(signin)
            return

        self.session.post(f"{PORTAL_URL}/portal/api/v2/oauth2/extension/code-grant/update",
                          headers=signin_headers, json={})

        flow_headers = dict(signin_headers)
        flow_headers["Referer"] = f"{PORTAL_URL}/portal/oauth2/verification-method?client_id=pay2-mobile-app-client&mode=navigation-2fa"
        flow = self.session.post(
            f"{PORTAL_URL}/portal/api/v2/oauth2/extension/code-grant/update",
            headers=flow_headers,
            json={"params": {"extension_id": "user-main-2fa-v1",
                             "data": {"type": "SELECT_FLOW",
                                      "payload": {"flow": "OTL", "sign_in_method": "MOBILE",
                                                  "base_url": f"{PORTAL_URL}/portal/oauth2/l"}}}},
        ).json()
        if flow["header"]["resultCode"] != "S0000":
            raise OpPayPayLoginError(flow)

        poll_headers = dict(flow_headers)
        poll_headers["Referer"] = f"{PORTAL_URL}/portal/oauth2/otl-request?client_id=pay2-mobile-app-client&mode=navigation-2fa"
        poll = self.session.post(
            f"{PORTAL_URL}/portal/api/v2/oauth2/extension/code-grant/side-channel/next-action-polling",
            headers=poll_headers,
            json={"waitUntil": "PT5S"},
        ).json()
        if poll["header"]["resultCode"] != "S0000":
            raise OpPayPayLoginError(poll)

    def login_confirm(self, otl_id: str) -> None:
        if "https://" in otl_id:
            otl_id = otl_id.replace(f"{PORTAL_URL}/portal/oauth2/l?id=", "")

        headers = self._portal_headers(json_body=True)
        headers["Referer"] = f"{PORTAL_URL}/portal/oauth2/l?id={otl_id}&client_id=pay2-mobile-app-client"

        confirm = self.session.post(
            f"{PORTAL_URL}/portal/api/v2/oauth2/extension/sign-in/2fa/otl/verify",
            headers=headers,
            json={"code": otl_id},
        ).json()
        if confirm["header"]["resultCode"] != "S0000":
            raise OpPayPayLoginError(confirm)

        complete = self.session.post(
            f"{PORTAL_URL}/portal/api/v2/oauth2/extension/code-grant/update",
            headers=headers,
            json={"params": {"extension_id": "user-main-2fa-v1",
                             "data": {"type": "COMPLETE_OTL", "payload": None}}},
        ).json()
        if complete["header"]["resultCode"] != "S0000":
            raise OpPayPayLoginError(complete)

        self._finish_token_exchange(complete)

    def _finish_token_exchange(self, grant_response: dict) -> None:
        try:
            uri = grant_response["payload"]["redirectUrl"].replace("paypay://oauth2/callback?", "").split("&")
        except KeyError:
            try:
                uri = grant_response["payload"]["redirect_uri"].replace("paypay://oauth2/callback?", "").split("&")
            except KeyError:
                raise OpPayPayLoginError("redirect_uri が見つかりませんでした")

        headers = dict(self.session.headers)
        headers.pop("Device-Lock-Type", None)
        headers.pop("Device-Lock-App-Setting", None)

        token = self.session.post(
            f"{BASE_URL}/bff/v2/oauth2/token",
            headers=headers,
            data={
                "clientId": "pay2-mobile-app-client",
                "redirectUri": "paypay://oauth2/callback",
                "code": uri[0].replace("code=", ""),
                "codeVerifier": self.code_verifier,
            },
            params={"payPayLang": "ja"},
        ).json()
        if token["header"]["resultCode"] != "S0000":
            raise OpPayPayLoginError(token)

        self.access_token = token["payload"]["accessToken"]
        self.refresh_token = token["payload"]["refreshToken"]
        self.session.headers["Authorization"] = f"Bearer {self.access_token}"
        self.session.headers["Content-Type"] = "application/json"
        self.session.headers.update(device_state())

    def _portal_headers(self, json_body: bool = False) -> dict:
        h = {
            "Accept": "application/json, text/plain, */*" if json_body else "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "ja-JP,ja;q=0.9",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Host": "www.paypay.ne.jp",
            "Pragma": "no-cache",
            "User-Agent": ios_27_webview_user_agent(),
        }
        h.update(ios_27_portal_headers())
        if json_body:
            h.update({
                "Accept": "application/json, text/plain, */*",
                "Client-Id": "pay2-mobile-app-client",
                "Client-OS-Type": "IOS",
                "Client-OS-Version": DEVICE["os_version"],
                "Client-Type": "PAYPAYAPP",
                "Client-Version": VERSION,
                "Content-Type": "application/json",
                "Origin": PORTAL_URL,
                "Referer": f"{PORTAL_URL}/portal/oauth2/sign-in?client_id=pay2-mobile-app-client&mode=landing",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            })
        return h

    def get_balance(self) -> Balance:
        self._require_token()
        params = {
            "includePendingBonusLite": "false",
            "includePending": "true",
            "noCache": "true",
            "includeKycInfo": "true",
            "includePayPaySecuritiesInfo": "true",
            "includePointInvestmentInfo": "true",
            "includePayPayBankInfo": "true",
            "includeGiftVoucherInfo": "true",
            "payPayLang": "ja",
        }
        response = self.request("get", f"{BASE_URL}/bff/v1/getBalanceInfo", params=params)

        wallet = response["payload"]["walletDetail"]
        summary = response["payload"]["walletSummary"]
        try:
            money = wallet["emoneyBalanceInfo"]["balance"]
        except KeyError:
            money = None
        return Balance(
            money=money,
            money_light=wallet["prepaidBalanceInfo"]["balance"],
            all_balance=summary["allTotalBalanceInfo"]["balance"],
            useable_balance=summary["usableBalanceInfoWithoutCashback"]["balance"],
            points=wallet["cashBackBalanceInfo"]["balance"],
            raw=response,
        )

    def create_p2pcode(self, amount: int | None = None) -> dict:
        self._require_token()
        payload = {"amount": None, "sessionId": None}
        if amount is not None:
            payload["amount"] = amount
            payload["sessionId"] = str(uuid4())
        response = self.request("post", f"{BASE_URL}/bff/v1/createP2PCode",
                                json=payload, params={"payPayLang": "ja"})
        return response

    def get_barcode_info(self, code: str) -> dict:
        self._require_token()
        if "https://" not in code:
            code = f"https://qr.paypay.ne.jp/{code}"
        return self.request("get", f"{BASE_URL}/bff/v2/getBarcodeInfo",
                            params={"code": code, "payPayLang": "ja"})

    def set_money_priority(self, paypay_money: bool) -> dict:
        self._require_token()
        payload = {"moneyPriority": "MONEY_FIRST" if paypay_money else "MONEY_LITE_FIRST"}
        return self.request("post", f"{BASE_URL}/p2p/v1/setMoneyPriority",
                            json=payload, params={"payPayLang": "ja"})

    def pay_request_link(self, code: str, money_first: bool) -> dict:
        self._require_token()
        if "https://" in code:
            code = code.replace("https://qr.paypay.ne.jp/", "")

        barcode = self.request("get", f"{BASE_URL}/bff/v2/getBarcodeInfo",
                               params={"code": f"https://qr.paypay.ne.jp/{code}",
                                       "payPayLang": "ja", "isScannedFromFile": "false"})
        dynamic = barcode["payload"]["codeInfo"]["dynamicCodeInfo"]
        payload = {
            "requestId": str(uuid4()),
            "merchantId": dynamic["merchantInfo"]["merchantId"],
            "storeId": "",
            "stickerId": "",
            "amount": dynamic["amount"],
            "currency": "JPY",
            "paymentMethodId": barcode["payload"]["paymentMethodInfo"]["paymentMethodIdString"],
            "paymentMethodType": "WALLET",
            "agreeSimilarTransactionFlag": False,
            "code": dynamic["code"],
            "merchantOrderId": dynamic["merchantOrderId"],
            "mode": "DYNAMIC_QR",
        }

        self.set_money_priority(paypay_money=money_first)
        return self.request("post", f"{BASE_URL}/bff/v2/executePayment",
                            json=payload, params={"payPayLang": "ja"})

    def alive(self) -> bool:
        self._require_token()
        params = {"payPayLang": "ja"}
        self.request("get", f"{BASE_URL}/bff/v1/getGlobalServiceStatus", params=params)
        self.request("post", f"{BASE_URL}/bff/v4/getHomeDisplayInfo", params=params, json={
            "abTestFlags": {"dedupeFeatureAndFavoritesTab": False},
            "excludeMissionBannerInfoFlag": False,
            "excludeTobaccoPolicyBannerFlag": True,
            "includeBeginnerFlag": False,
            "includeSkinInfoFlag": False,
            "networkStatus": "WIFI",
        })
        self.request("post", f"{BASE_URL}/bff/v1/getFeatureFlagInfo", params=params, json={
            "flagNames": ["enable_home_screen_favoriting_suggestions", "home_screen_all_entry_point_ab_test"]
        })
        return True