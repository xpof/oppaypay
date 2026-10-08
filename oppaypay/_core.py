"""PayPay モバイル API クライアント本体

PayPaython-mobile (https://github.com/taka-4602/PayPaython-mobile) を
ベースに oppapay 向けに整理したもの。
"""
import random
import time
from typing import NamedTuple
from uuid import uuid4

import requests

from .exceptions import OpPayPayError, OpPayPayLoginError, OpPayPayNetworkError

VERSION = "5.57.0"
BASE_URL = "https://app4.paypay.ne.jp"
PORTAL_URL = "https://www.paypay.ne.jp"


def _vector(r1, r2, r3, precision=8):
    v1 = f"{random.uniform(*r1):.{precision}f}"
    v2 = f"{random.uniform(*r2):.{precision}f}"
    v3 = f"{random.uniform(*r3):.{precision}f}"
    return f"{v1}_{v2}_{v3}"


def _device_state():
    return {
        "Device-Orientation": _vector((2.2, 2.6), (-0.2, -0.05), (-0.05, 0.1)),
        "Device-Orientation-2": _vector((2.0, 2.6), (-0.2, -0.05), (-0.05, 0.2)),
        "Device-Rotation": _vector((-0.8, -0.6), (0.65, 0.8), (-0.12, -0.04)),
        "Device-Rotation-2": _vector((-0.85, -0.4), (0.53, 0.9), (-0.15, -0.03)),
        "Device-Acceleration": _vector((-0.35, 0.0), (-0.01, 0.3), (-0.1, 0.1)),
        "Device-Acceleration-2": _vector((0.01, 0.04), (-0.04, 0.09), (-0.03, 0.1)),
    }


class Balance(NamedTuple):
    money: int | None          # PayPayマネー
    money_light: int           # PayPayマネーライト
    all_balance: int           # 合計残高
    useable_balance: int       # 使用可能残高
    points: int                # ポイント
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

        self.session = requests.Session()
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

        self.access_token: str | None = None
        self.refresh_token: str | None = None

        self._build_headers()
        if access_token:
            self.access_token = access_token
            self.session.headers["Authorization"] = f"Bearer {access_token}"
            self.session.headers["Content-Type"] = "application/json"

    # ------------------------------------------------ 基盤
    def _build_headers(self):
        h = {
            "Accept": "*/*",
            "Accept-Charset": "UTF-8",
            "Accept-Encoding": "gzip",
            "Client-Mode": "NORMAL",
            "Client-OS-Release-Version": "10",
            "Client-OS-Type": "ANDROID",
            "Client-OS-Version": "29.0.0",
            "Client-Type": "PAYPAYAPP",
            "Client-UUID": self.client_uuid,
            "Client-Version": VERSION,
            "Connection": "Keep-Alive",
            "Content-Type": "application/x-www-form-urlencoded",
            "Device-Brand-Name": "KDDI",
            "Device-Hardware-Name": "qcom",
            "Device-In-Call": "false",
            "Device-Lock-App-Setting": "false",
            "Device-Lock-Type": "NONE",
            "Device-Manufacturer-Name": "samsung",
            "Device-Name": "SCV38",
            "Device-UUID": self.device_uuid,
            "Host": "app4.paypay.ne.jp",
            "Is-Emulator": "false",
            "Network-Status": "WIFI",
            "System-Locale": "ja",
            "Timezone": "Asia/Tokyo",
            "User-Agent": f"PaypayApp/{VERSION} Android10",
        }
        h.update(_device_state())
        self.session.headers = h

    def request(self, method: str, url: str, **kwargs) -> dict:
        if method.lower() == "get":
            response = self.session.get(url, **kwargs)
        elif method.lower() == "post":
            response = self.session.post(url, **kwargs)
        else:
            raise ValueError("GET または POST のみ対応しています")

        try:
            response_json = response.json()
        except Exception:
            raise OpPayPayNetworkError(f"JSON のパースに失敗しました: {response.text[:200]}")

        header = response_json.get("header", {})
        if header:
            code = header.get("resultCode")
            if code == "S0001":
                raise OpPayPayLoginError(f"アクセストークンが無効です: {header.get('resultMessage')}")
            elif code == "S0000" or code == "S4002":
                pass
            else:
                try:
                    if response_json["error"]["displayErrorResponse"]["description"] == "しばらく時間をおいて、再度お試しください":
                        raise OpPayPayError("レート制限に達しました")
                except KeyError:
                    pass
                raise OpPayPayError(f"{code}: {header.get('resultMessage')}")
        return response_json

    def _require_token(self):
        if not self.access_token:
            raise OpPayPayLoginError("先にログインしてください")

    # ------------------------------------------------ ログイン
    def login_start(self) -> None:
        """仮ログインを開始する。2FA(OTL)承認待ちの状態になる。"""
        import pkce  # 遅延import: 未使用時は pkce 不要

        self.access_token = None
        self.refresh_token = None
        self.code_verifier, code_challenge = pkce.generate_pkce_pair(43)

        payload = {
            "clientId": "pay2-mobile-app-client",
            "clientAppVersion": VERSION,
            "clientOsVersion": "29.0.0",
            "clientOsType": "ANDROID",
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

        # 未登録デバイス: OTL (ワンタイムリンク) 承認待ちへ
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
        """OTL (verifycode) で 2FA を完了し、トークンを取得する。"""
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
        self.session.headers.update(_device_state())

    def _portal_headers(self, json_body: bool = False) -> dict:
        ua = (f"Mozilla/5.0 (Linux; Android 10; SCV38 Build/QP1A.190711.020; wv) "
              f"AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/132.0.6834.163 "
              f"Mobile Safari/537.36 jp.pay2.app.android/{VERSION}")
        h = {
            "Accept": "application/json, text/plain, */*" if json_body else "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "ja-JP,ja;q=0.9",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Host": "www.paypay.ne.jp",
            "Pragma": "no-cache",
            "sec-ch-ua": '"Not A(Brand";v="8", "Chromium";v="132", "Android WebView";v="132"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "User-Agent": ua,
            "X-Requested-With": "jp.ne.paypay.android.app",
        }
        if json_body:
            h.update({
                "Accept": "application/json, text/plain, */*",
                "Client-Id": "pay2-mobile-app-client",
                "Client-OS-Type": "ANDROID",
                "Client-OS-Version": "29.0.0",
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

    # ------------------------------------------------ 残高
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

    # ------------------------------------------------ 請求リンク / P2Pコード
    def create_p2pcode(self, amount: int | None = None) -> dict:
        """請求リンク(qr.paypay.ne.jp/...)または友だち登録用URLを生成する"""
        self._require_token()
        payload = {"amount": None, "sessionId": None}
        if amount is not None:
            payload["amount"] = amount
            payload["sessionId"] = str(uuid4())
        response = self.request("post", f"{BASE_URL}/bff/v1/createP2PCode",
                                json=payload, params={"payPayLang": "ja"})
        return response

    def get_barcode_info(self, code: str) -> dict:
        """請求リンクから金額・相手情報を取得する"""
        self._require_token()
        if "https://" not in code:
            code = f"https://qr.paypay.ne.jp/{code}"
        return self.request("get", f"{BASE_URL}/bff/v2/getBarcodeInfo",
                            params={"code": code, "payPayLang": "ja"})

    def set_money_priority(self, paypay_money: bool) -> dict:
        """支払いの優先残高を設定する。True=マネー優先、False=マネーライト優先"""
        self._require_token()
        payload = {"moneyPriority": "MONEY_FIRST" if paypay_money else "MONEY_LITE_FIRST"}
        return self.request("post", f"{BASE_URL}/p2p/v1/setMoneyPriority",
                            json=payload, params={"payPayLang": "ja"})

    def pay_request_link(self, code: str, money_first: bool) -> dict:
        """請求リンクを支払う。money_first でマネー/マネーライトを切り替える"""
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

    # ------------------------------------------------ Bot検知対策
    def alive(self) -> bool:
        """アプリと同じ無駄リクエストを送り、Bot検知を回避する"""
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
