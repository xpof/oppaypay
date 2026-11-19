import random
import time
import logging
import secrets
import hashlib
import re
import threading
import json
from typing import NamedTuple
from urllib.parse import parse_qs, urlparse
from uuid import uuid4
from curl_cffi import requests as curl_requests
import pkce

from ._fingerprint import select_profile
from ._sensors import generate_device_state, update_header_device_state
from ._awswaf import solve_aws_waf_challenge
from ._alive import AliveSimulator
from .exceptions import (
    OpPayPayError,
    OpPayPayLoginError,
    OpPayPayNetworkError,
    OpPayPayBotDetectedError,
    OpPayPayEKYCRequiredError,
    OpPayPayAccountLockedError,
    OpPayPayRateLimitError,
)

log = logging.getLogger("oppaypay.core")

VERSION = "5.57.0"
BASE_URL = "https://app4.paypay.ne.jp"
WEB_PORTAL_URL = "https://www.paypay.ne.jp"


class Balance(NamedTuple):
    money: int | None
    money_light: int | None
    all_balance: int | None
    useable_balance: int | None
    points: int | None
    bank_balance: int | None
    securities_balance: int | None
    gift_voucher_balance: int | None
    raw: dict


class PayPayCore:
    def __init__(
        self,
        phone: str | None = None,
        password: str | None = None,
        device_uuid: str | None = None,
        client_uuid: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
        proxy: str | None = None,
        humanize: bool = True,
    ):
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
        self._otp_prefix: str | None = None

        self._alive_simulator: AliveSimulator | None = None
        self._alive_thread: threading.Thread | None = None
        self._alive_stop_event = threading.Event()

        web_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 26_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/23G71"
        self.session = curl_requests.Session(
            impersonate=select_profile(web_ua),
            proxies={"http": proxy, "https": proxy} if proxy else None,
            timeout=30,
        )

        self.access_token: str | None = access_token
        self.code_verifier: str | None = None

        device_state = generate_device_state()

        self._mobile_headers = {
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
            "Device-Hardware-Name": "V57AP",
            "Device-In-Call": "false",
            "Device-Lock-App-Setting": "false",
            "Device-Lock-Type": "NONE",
            "Device-Manufacturer-Name": "Apple",
            "Device-Name": "iPhone18,3",
            "Device-Orientation": device_state.device_orientation,
            "Device-Orientation-2": device_state.device_orientation_2,
            "Device-Rotation": device_state.device_rotation,
            "Device-Rotation-2": device_state.device_rotation_2,
            "Device-UUID": self.device_uuid,
            "FontSize": "1.0",
            "Host": "app4.paypay.ne.jp",
            "Is-Emulator": "false",
            "Network-Status": "WIFI",
            "System-Locale": "ja",
            "Timezone": "Asia/Tokyo",
            "User-Agent": f"PaypayApp/{VERSION} iPhone18,3",
            "Client-Latitude": "35.665558",
            "Client-Longitude": "139.669597",
        }

        self.session.headers.update(self._mobile_headers)

        if self.access_token:
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

    def _api_request(self, method: str, url: str, max_retries: int = 3, **kwargs) -> dict:
        last_exception = None

        for attempt in range(max_retries):
            self._human_delay(url)
            try:
                headers_to_use = self._mobile_headers.copy()
                if self.access_token:
                    headers_to_use["Authorization"] = f"Bearer {self.access_token}"
                if "Content-Type" not in headers_to_use:
                    headers_to_use["Content-Type"] = "application/json"

                if "headers" in kwargs:
                    headers_to_use.update(kwargs.pop("headers"))

                if method.lower() == "get":
                    response = self.session.get(url, headers=headers_to_use, **kwargs)
                elif method.lower() == "post":
                    response = self.session.post(url, headers=headers_to_use, **kwargs)
                elif method.lower() == "delete":
                    response = self.session.delete(url, headers=headers_to_use, **kwargs)
                else:
                    raise ValueError("Invalid HTTP method.")

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 0))
                    wait = retry_after if retry_after > 0 else (secrets.randbelow(300) / 10.0) + 15.0
                    log.warning(f"Rate limited (429). Waiting {wait:.1f}s...")
                    time.sleep(wait)
                    continue
                elif response.status_code >= 500:
                    if attempt < max_retries - 1:
                        time.sleep((secrets.randbelow(200) / 100.0) + 1.0)
                        continue
                    raise OpPayPayNetworkError(f"Server error {response.status_code}")

                try:
                    response_json = response.json()
                except Exception:
                    raise OpPayPayNetworkError(f"Failed to parse JSON response: {response.text[:200]}")

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

            except (OpPayPayBotDetectedError, OpPayPayRateLimitError, OpPayPayLoginError):
                raise
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    time.sleep((secrets.randbelow(100) / 100.0) + 0.5)
                else:
                    log.error(f"API request failed after {max_retries} attempts: {e}")

        raise last_exception or OpPayPayNetworkError("Unknown network error")

    def _web_request(self, method: str, url: str, headers: dict, allow_redirects: bool = True, **kwargs) -> curl_requests.Response:
        self._human_delay(url)

        if method.lower() == "get":
            response = self.session.get(url, headers=headers, allow_redirects=allow_redirects, **kwargs)
        elif method.lower() == "post":
            response = self.session.post(url, headers=headers, allow_redirects=allow_redirects, **kwargs)
        else:
            raise ValueError("Invalid HTTP method.")

        if response.status_code == 202 and "x-amzn-waf-action" in response.headers:
            log.info("AWS WAF challenge detected. Solving...")
            aws_waf_token = solve_aws_waf_challenge(response.text, headers.get("User-Agent", ""))
            self.session.cookies.set("aws-waf-token", aws_waf_token, domain=".paypay.ne.jp")
            self._human_delay(url)

            if method.lower() == "get":
                response = self.session.get(url, headers=headers, allow_redirects=allow_redirects, **kwargs)
            else:
                response = self.session.post(url, headers=headers, allow_redirects=allow_redirects, **kwargs)

        return response

    def start_alive_simulator(self, duration_minutes: int = 60, loop: bool = True):
        if self._alive_thread and self._alive_thread.is_alive():
            log.warning("AliveSimulator はすでに起動しています。")
            return

        if not self._alive_simulator:
            self._alive_simulator = AliveSimulator(self)

        self._alive_stop_event.clear()

        def _run():
            log.info("🌱 バックグラウンドで AliveSimulator を開始しました。")
            while not self._alive_stop_event.is_set():
                try:
                    self._alive_simulator.simulate_session(duration_minutes=duration_minutes)
                except Exception as e:
                    log.error(f"AliveSimulator 実行中にエラー: {e}")
                    time.sleep(10)

                if not loop:
                    break
            log.info("🌿 AliveSimulator を停止しました。")

        self._alive_thread = threading.Thread(target=_run, daemon=True)
        self._alive_thread.start()

    def stop_alive_simulator(self):
        if self._alive_thread and self._alive_thread.is_alive():
            log.info("AliveSimulator の停止シグナルを送信しました...")
            self._alive_stop_event.set()
            self._alive_thread.join(timeout=10)
            self._alive_thread = None
        else:
            log.info("AliveSimulator は起動していません。")

    def login_start(self):
        """Web版ログインフローを開始し、SMS OTPの準備をします"""
        if not self.phone or not self.password:
            raise OpPayPayLoginError("電話番号とパスワードが必要です")

        log.info(f"🌐 Web版ログインフロー開始: {self.phone}")

        # Web版ログイン用の一時的なヘッダー
        web_headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Content-Type": "application/json",
            "Origin": WEB_PORTAL_URL,
            "Referer": f"{WEB_PORTAL_URL}/app/account/sign-in",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }

        url = f"{WEB_PORTAL_URL}/app/v1/oauth/token"
        payload = {
            "scope": "SIGN_IN",
            "client_uuid": self.client_uuid,
            "grant_type": "password",
            "username": self.phone,
            "password": self.password,
            "add_otp_prefix": True,
            "language": "ja",
        }

        try:
            response = self._web_request("POST", url, headers=web_headers, json=payload)
            data = response.json()

            # OTPが要求された場合
            if "otp_prefix" in data.get("payload", {}):
                self._otp_prefix = data["payload"]["otp_prefix"]
                log.info(f"📱 SMS OTPが要求されました。Prefix: {self._otp_prefix}")
                log.info("👉 login_confirm() にSMSの4桁コードを入力してください。")
                self._login_headers = web_headers
                return

            # トークンが直接返ってきた場合（2FA不要なアカウントの場合）
            if "access_token" in data:
                self._set_tokens(data)
                log.info("✅ ログイン成功 (2FA不要)")
                return

            raise OpPayPayLoginError(f"予期しないレスポンス: {data}")

        except Exception as e:
            raise OpPayPayLoginError(f"ログイン開始失敗: {e}")

    def login_confirm(self, otp_code: str):
        """SMS OTPコードを入力して認証を完了し、トークンを取得します"""
        if not self._otp_prefix:
            raise OpPayPayLoginError("login_start() を先に実行してください")

        # コードから数字のみ抽出
        otp_digits = re.sub(r"\D", "", otp_code)
        if len(otp_digits) != 4:
            raise OpPayPayLoginError("OTPコードは4桁の数字を入力してください")

        log.info(f"🔢 OTP認証実行: {otp_digits}")

        url = f"{WEB_PORTAL_URL}/app/v1/oauth/token"
        payload = {
            "scope": "SIGN_IN",
            "client_uuid": self.client_uuid,
            "grant_type": "otp",
            "username": self.phone,
            "password": self.password,
            "otp": otp_digits,
            "otp_prefix": self._otp_prefix,
            "language": "ja",
        }

        web_headers = self._login_headers.copy() if self._login_headers else {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Content-Type": "application/json",
            "Origin": WEB_PORTAL_URL,
            "Referer": f"{WEB_PORTAL_URL}/app/account/sign-in",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

        try:
            response = self._web_request("POST", url, headers=web_headers, json=payload)
            data = response.json()

            if "access_token" in data:
                self._set_tokens(data)
                log.info("✅ OTP認証成功！トークンを取得し、モバイル用セッションに切り替えました。")
            else:
                raise OpPayPayLoginError(f"OTP認証失敗: {data}")

        except Exception as e:
            raise OpPayPayLoginError(f"OTP認証失敗: {e}")

    def _set_tokens(self, data: dict):
        """トークンを設定し、ヘッダーをモバイル用に完全に切り替える"""
        self.access_token = data.get("access_token")
        self.refresh_token = data.get("refresh_token")

        if self.access_token:
            # モバイル用ヘッダーに Authorization を追加
            self._mobile_headers["Authorization"] = f"Bearer {self.access_token}"
            self._mobile_headers["Content-Type"] = "application/json"

            # セッションのヘッダーをモバイル用に完全に上書き
            self.session.headers.clear()
            self.session.headers.update(self._mobile_headers)

    def refresh_session(self) -> bool:
        if not getattr(self, "refresh_token", None):
            raise OpPayPayLoginError("refresh_token が存在しません。再度ログインしてください。")

        headers = self._mobile_headers.copy()
        if "Device-Lock-Type" in headers:
            del headers["Device-Lock-Type"]
        if "Device-Lock-App-Setting" in headers:
            del headers["Device-Lock-App-Setting"]

        refresh_url = f"{BASE_URL}/v2/oauth2/refresh"
        refresh_data = {
            "clientId": "pay2-mobile-app-client",
            "refresh_token": self.refresh_token,
        }

        get_token = self._api_request(
            "post",
            refresh_url,
            headers=headers,
            data=refresh_data,
            params={"payPayLang": "ja"},
            timeout=60,
        )

        if get_token.get("header", {}).get("resultCode") != "S0000":
            raise OpPayPayLoginError(f"トークン更新に失敗しました: {get_token}")

        payload = get_token.get("payload", {})
        self.access_token = payload.get("accessToken")
        self.refresh_token = payload.get("refreshToken", self.refresh_token)

        if not self.access_token:
            raise OpPayPayLoginError("更新後の access_token が見つかりませんでした")

        self.session.headers["Authorization"] = f"Bearer {self.access_token}"
        self.session.headers["content-type"] = "application/json"
        self.session.headers = update_header_device_state(self.session.headers)

        log.info("✅ セッショントークンの更新に成功しました。")
        return True

    def alive(self) -> bool:
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")

        params = {"payPayLang": "ja"}
        self._api_request("get", f"{BASE_URL}/bff/v1/getGlobalServiceStatus", params=params)
        self._api_request(
            "post",
            f"{BASE_URL}/bff/v4/getHomeDisplayInfo",
            params=params,
            json={
                "abTestFlags": {"dedupeFeatureAndFavoritesTab": False},
                "excludeMissionBannerInfoFlag": False,
                "excludeTobaccoPolicyBannerFlag": True,
                "includeBeginnerFlag": False,
                "includeSkinInfoFlag": False,
                "networkStatus": "WIFI",
            },
        )
        self._api_request(
            "post",
            f"{BASE_URL}/bff/v1/getFeatureFlagInfo",
            params=params,
            json={
                "flagNames": [
                    "enable_home_screen_favoriting_suggestions",
                    "home_screen_all_entry_point_ab_test",
                ]
            },
        )
        return True

    def get_balance(self) -> Balance:
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")

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
        response = self._api_request("get", f"{BASE_URL}/bff/v1/getBalanceInfo", params=params)

        wallet_detail = response.get("payload", {}).get("walletDetail", {})
        wallet_summary = response.get("payload", {}).get("walletSummary", {})

        money = None
        for key in ["emoneyBalanceInfo", "moneyBalanceInfo"]:
            if key in wallet_detail:
                try:
                    money = wallet_detail[key]["balance"]
                    break
                except (KeyError, TypeError):
                    pass

        money_light = None
        if "prepaidBalanceInfo" in wallet_detail:
            try:
                money_light = wallet_detail["prepaidBalanceInfo"]["balance"]
            except (KeyError, TypeError):
                pass

        points = None
        for key in ["cashBackBalanceInfo", "pointBalanceInfo", "paypayPointBalanceInfo"]:
            if key in wallet_detail:
                try:
                    points = wallet_detail[key]["balance"]
                    break
                except (KeyError, TypeError):
                    pass

        bank_balance = None
        if "payPayBankInfo" in wallet_detail:
            try:
                bank_balance = wallet_detail["payPayBankInfo"]["balance"]
            except (KeyError, TypeError):
                pass

        securities_balance = None
        if "payPaySecuritiesInfo" in wallet_detail:
            try:
                securities_balance = wallet_detail["payPaySecuritiesInfo"]["balance"]
            except (KeyError, TypeError):
                pass

        gift_voucher_balance = None
        if "giftVoucherInfo" in wallet_detail:
            try:
                gift_voucher_balance = wallet_detail["giftVoucherInfo"]["balance"]
            except (KeyError, TypeError):
                pass

        all_balance = None
        if "allTotalBalanceInfo" in wallet_summary:
            try:
                all_balance = wallet_summary["allTotalBalanceInfo"]["balance"]
            except (KeyError, TypeError):
                pass

        useable_balance = None
        if "usableBalanceInfoWithoutCashback" in wallet_summary:
            try:
                useable_balance = wallet_summary["usableBalanceInfoWithoutCashback"]["balance"]
            except (KeyError, TypeError):
                pass

        return Balance(
            money=money,
            money_light=money_light,
            all_balance=all_balance,
            useable_balance=useable_balance,
            points=points,
            bank_balance=bank_balance,
            securities_balance=securities_balance,
            gift_voucher_balance=gift_voucher_balance,
            raw=response,
        )

    def create_p2pcode(self, amount: int = None):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        payload = {"amount": None, "sessionId": None}
        if amount:
            payload["amount"] = amount
            payload["sessionId"] = str(uuid4())
        return self._api_request("post", f"{BASE_URL}/bff/v1/createP2PCode", json=payload, params={"payPayLang": "ja"})

    def delete_p2pcode(self, code_id: str):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        return self._api_request("delete", f"{BASE_URL}/p2p/v1/p2pCodes/{code_id}", params={"payPayLang": "ja"})

    def get_barcode_info(self, url: str):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        if url.startswith("https://qr.paypay.ne.jp/"):
            url = url[len("https://qr.paypay.ne.jp/"):]
        url = url.rstrip("/")
        return self._api_request(
            "get",
            f"{BASE_URL}/bff/v2/getBarcodeInfo?code=https://qr.paypay.ne.jp/{url}",
            params={"payPayLang": "ja", "isScannedFromFile": "false"},
        )

    def set_money_priority(self, paypay_money: bool = False):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        payload = {"moneyPriority": "MONEY_FIRST" if paypay_money else "MONEY_LITE_FIRST"}
        return self._api_request("post", f"{BASE_URL}/p2p/v1/setMoneyPriority", json=payload, params={"payPayLang": "ja"})

    def pay_qr_code(self, url: str):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        if url.startswith("https://qr.paypay.ne.jp/"):
            url = url[len("https://qr.paypay.ne.jp/"):]
        url = url.rstrip("/")

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
            "mode": "DYNAMIC_QR",
        }
        return self._api_request("post", f"{BASE_URL}/bff/v2/executePayment", json=payload, params={"payPayLang": "ja"})

    def send_money(self, phone: str, amount: int, message: str = ""):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        if "-" in phone:
            phone = phone.replace("-", "")

        payload = {
            "sessionId": str(uuid4()),
            "amount": amount,
            "currency": "JPY",
            "receiverPhoneNumber": phone,
            "message": message,
            "paymentMethodId": "",
            "paymentMethodType": "WALLET",
        }
        return self._api_request("post", f"{BASE_URL}/p2p/v1/sendMoney", json=payload, params={"payPayLang": "ja"})

    def charge_money(self, amount: int, payment_method_id: str):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        payload = {
            "amount": amount,
            "currency": "JPY",
            "paymentMethodId": payment_method_id,
            "sessionId": str(uuid4()),
        }
        return self._api_request("post", f"{BASE_URL}/bff/v1/charge", json=payload, params={"payPayLang": "ja"})

    def withdraw_money(self, amount: int, bank_account_id: str):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        payload = {
            "amount": amount,
            "currency": "JPY",
            "bankAccountId": bank_account_id,
            "sessionId": str(uuid4()),
        }
        return self._api_request("post", f"{BASE_URL}/bff/v1/withdraw", json=payload, params={"payPayLang": "ja"})

    def get_registered_banks(self):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        return self._api_request("get", f"{BASE_URL}/bff/v1/getRegisteredBanks", params={"payPayLang": "ja"})

    def get_registered_cards(self):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        return self._api_request("get", f"{BASE_URL}/bff/v1/getRegisteredCards", params={"payPayLang": "ja"})

    def get_users_self(self) -> dict:
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")

        url = f"{WEB_PORTAL_URL}/app/v2/users/self"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "User-Agent": self.session.headers.get("User-Agent", ""),
            "Referer": f"{WEB_PORTAL_URL}/app/smartpayment/web/link",
        }
        res = self._web_request("get", url, headers=headers)
        data = res.json()
        if data.get("result_info", {}).get("result_status") != "S":
            raise OpPayPayError(data)
        return data

    def get_profile(self) -> dict:
        return self.get_users_self()

    def get_kyc_status(self):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        return self._api_request("get", f"{BASE_URL}/bff/v1/getKycStatus", params={"payPayLang": "ja"})

    def get_notifications(self, limit: int = 20):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        return self._api_request("get", f"{BASE_URL}/bff/v1/getNotifications", params={"payPayLang": "ja", "limit": str(limit)})

    def mark_notification_read(self, notification_id: str):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        return self._api_request(
            "post",
            f"{BASE_URL}/bff/v1/markNotificationRead",
            json={"notificationId": notification_id},
            params={"payPayLang": "ja"},
        )

    def get_campaigns(self):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        return self._api_request("get", f"{BASE_URL}/bff/v1/getCampaigns", params={"payPayLang": "ja"})

    def get_coupons(self):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        return self._api_request("get", f"{BASE_URL}/bff/v1/getCoupons", params={"payPayLang": "ja"})

    def get_transaction_history(self, limit: int = 20, offset: int = 0):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        return self._api_request(
            "get",
            f"{BASE_URL}/bff/v1/getTransactionHistory",
            params={"payPayLang": "ja", "limit": str(limit), "offset": str(offset)},
        )

    def get_payment_history(self, limit: int = 20, offset: int = 0):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        return self._api_request(
            "get",
            f"{BASE_URL}/bff/v1/getPaymentHistory",
            params={"payPayLang": "ja", "limit": str(limit), "offset": str(offset)},
        )

    def get_login_history(self, limit: int = 20):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        return self._api_request("get", f"{BASE_URL}/bff/v1/getLoginHistory", params={"payPayLang": "ja", "limit": str(limit)})

    def get_devices(self):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        return self._api_request("get", f"{BASE_URL}/bff/v1/getDevices", params={"payPayLang": "ja"})

    def get_bill_info(self, bill_id: str):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        return self._api_request("get", f"{BASE_URL}/bff/v1/getBillInfo/{bill_id}", params={"payPayLang": "ja"})

    def pay_bill(self, bill_id: str, payment_method_id: str):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        payload = {
            "billId": bill_id,
            "paymentMethodId": payment_method_id,
            "sessionId": str(uuid4()),
        }
        return self._api_request("post", f"{BASE_URL}/bff/v1/payBill", json=payload, params={"payPayLang": "ja"})

    def get_gift_voucher_balance(self):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        return self._api_request("get", f"{BASE_URL}/bff/v1/getGiftVoucherBalance", params={"payPayLang": "ja"})

    def get_securities_balance(self):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        return self._api_request("get", f"{BASE_URL}/bff/v1/getSecuritiesBalance", params={"payPayLang": "ja"})
