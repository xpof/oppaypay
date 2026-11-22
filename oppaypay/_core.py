from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from curl_cffi import requests as curl_requests

from .exceptions import (
    OpPayPayError,
    OpPayPayLoginError,
    OpPayPayNetworkError,
    OpPayPayBotDetectedError,
    OpPayPayAccountLockedError,
    OpPayPayRateLimitError,
)


class PayPayCore:

    def __init__(
        self,
        phone: Optional[str] = None,
        password: Optional[str] = None,
        device_uuid: Optional[str] = None,
        client_uuid: Optional[str] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        proxy: Optional[str] = None,
    ):
        self.phone = phone.replace("-", "") if phone else None
        self.password = password
        self.device_uuid = device_uuid or str(uuid.uuid4())
        self.client_uuid = (client_uuid or str(uuid.uuid4())).upper()
        self.refresh_token = refresh_token
        self.access_token = access_token

        self._otp_reference_id: Optional[str] = None
        self._otp_prefix: Optional[str] = None

        self.session = curl_requests.Session(
            impersonate="chrome",
            proxies={"http": proxy, "https": proxy} if proxy else None,
            timeout=30.0,
        )

        self.headers = {
            "Accept": "*/*",
            "Accept-Charset": "UTF-8",
            "Accept-Encoding": "gzip",
            "Client-Mode": "NORMAL",
            "Client-OS-Release-Version": "17",
            "Client-OS-Type": "IOS",
            "Client-OS-Version": "17.0",
            "Client-Type": "PAYPAYAPP",
            "Client-UUID": self.client_uuid,
            "Client-Version": "5.57.0",
            "Connection": "Keep-Alive",
            "Content-Type": "application/json",
            "Device-Brand-Name": "Apple",
            "Device-Hardware-Name": "V57AP",
            "Device-In-Call": "false",
            "Device-Lock-App-Setting": "false",
            "Device-Lock-Type": "NONE",
            "Device-Manufacturer-Name": "Apple",
            "Device-Name": "iPhone18,3",
            "Device-UUID": self.device_uuid,
            "FontSize": "1.0",
            "Host": "app4.paypay.ne.jp",
            "Is-Emulator": "false",
            "Network-Status": "WIFI",
            "System-Locale": "ja",
            "Timezone": "Asia/Tokyo",
            "User-Agent": "PaypayApp/5.57.0 iPhone18,3",
            "Client-Latitude": "35.665558",
            "Client-Longitude": "139.669597",
        }

        if self.access_token:
            self.headers["Authorization"] = f"Bearer {self.access_token}"

    def _web_request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        web_headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Content-Type": "application/json",
            "Origin": "https://www.paypay.ne.jp",
            "Referer": "https://www.paypay.ne.jp/app/account/sign-in",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"iOS"',
        }
        if self.access_token:
            web_headers["Cookie"] = f"token={self.access_token}"

        url = f"https://www.paypay.ne.jp/{path.lstrip('/')}"
        resp = self.session.request(method, url, headers=web_headers, **kwargs)
        return _parse_web_response(resp)

    def login_start(self) -> Dict[str, Any]:
        if not self.phone or not self.password:
            raise OpPayPayLoginError("電話番号とパスワードが必要です")

        web_headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Content-Type": "application/json",
            "Origin": "https://www.paypay.ne.jp",
            "Referer": "https://www.paypay.ne.jp/app/account/sign-in",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"iOS"',
        }

        try:
            self.session.get("https://www.paypay.ne.jp/app/account/sign-in", headers=web_headers)
        except Exception:
            pass

        payload = {
            "scope": "SIGN_IN",
            "client_uuid": self.client_uuid,
            "grant_type": "password",
            "username": self.phone,
            "password": self.password,
            "add_otp_prefix": True,
            "language": "ja",
        }

        resp = self.session.post(
            "https://www.paypay.ne.jp/app/v1/oauth/token",
            headers=web_headers,
            json=payload,
        )
        data = _parse_web_response(resp)

        self.access_token = data.get("access_token")
        self.refresh_token = data.get("refresh_token")
        self._otp_reference_id = data.get("otp_reference_id")
        self._otp_prefix = data.get("otp_prefix")

        if not self.access_token and not self._otp_reference_id:
            raise OpPayPayLoginError(f"ログイン応答が不正です: {data}")

        return {
            "otp_required": not self.access_token,
            "otp_prefix": self._otp_prefix,
            "otp_reference_id": self._otp_reference_id,
        }

    def login_confirm(self, otp_code: str) -> str:
        if not self._otp_reference_id:
            raise OpPayPayLoginError("先に login_start() を実行してください")

        otp_digits = re.sub(r"\D", "", otp_code)
        if len(otp_digits) != 4:
            raise OpPayPayLoginError("OTPコードは4桁の数字を入力してください")

        web_headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Content-Type": "application/json",
            "Origin": "https://www.paypay.ne.jp",
            "Referer": "https://www.paypay.ne.jp/app/account/sign-in",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        }

        payload = {
            "scope": "SIGN_IN",
            "client_uuid": self.client_uuid,
            "grant_type": "otp",
            "otp_prefix": self._otp_prefix,
            "otp": otp_digits,
            "otp_reference_id": self._otp_reference_id,
            "username_type": "MOBILE",
            "language": "ja",
        }

        resp = self.session.post(
            "https://www.paypay.ne.jp/app/v1/oauth/token",
            headers=web_headers,
            json=payload,
        )
        data = _parse_web_response(resp)

        self.access_token = data.get("access_token")
        self.refresh_token = data.get("refresh_token")

        if not self.access_token:
            raise OpPayPayLoginError(f"OTP認証失敗: {data}")

        self.headers["Authorization"] = f"Bearer {self.access_token}"
        self.session.headers.clear()
        self.session.headers.update(self.headers)

        return self.access_token

    def resend_otp(self) -> Dict[str, Any]:
        if not self._otp_reference_id:
            raise OpPayPayLoginError("先に login_start() を実行してください")
        
        web_headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://www.paypay.ne.jp",
            "Referer": "https://www.paypay.ne.jp/app/account/sign-in",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        }
        
        resp = self.session.post(
            f"https://www.paypay.ne.jp/app/v1/otp/mobile/resend/{self._otp_reference_id}",
            headers=web_headers,
            json={"add_otp_prefix": "true"},
        )
        data = _parse_web_response(resp)
        self._otp_prefix = data.get("otp_prefix")
        return data

    def _api_request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        if not self.access_token:
            raise OpPayPayLoginError("先にログインしてください")

        headers_to_use = self.headers.copy()
        if "headers" in kwargs:
            headers_to_use.update(kwargs.pop("headers"))

        url = f"https://app4.paypay.ne.jp/{path.lstrip('/')}"
        resp = self.session.request(method, url, headers=headers_to_use, **kwargs)
        return _parse_mobile_response(resp)

    def get_balance(self) -> Dict[str, Any]:
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
        return self._api_request("GET", "bff/v1/getBalanceInfo", params=params)

    def get_profile(self) -> Dict[str, Any]:
        return self._api_request("GET", "bff/v1/getUserProfile", params={"payPayLang": "ja"})

    def send_money(self, phone: str, amount: int, message: str = "") -> Dict[str, Any]:
        if "-" in phone:
            phone = phone.replace("-", "")
        payload = {
            "sessionId": str(uuid.uuid4()),
            "amount": amount,
            "currency": "JPY",
            "receiverPhoneNumber": phone,
            "message": message,
            "paymentMethodId": "",
            "paymentMethodType": "WALLET",
        }
        return self._api_request("POST", "p2p/v3/executeP2PSendMoney", json=payload, params={"payPayLang": "ja"})

    def get_transaction_history(self, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        return self._api_request(
            "GET", "bff/v1/getTransactionHistory",
            params={"payPayLang": "ja", "limit": str(limit), "offset": str(offset)},
        )

    def get_payment_history(self, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        return self._api_request(
            "GET", "bff/v4/getPaymentHistory",
            params={"payPayLang": "ja", "limit": str(limit), "offset": str(offset)},
        )

    def get_login_history(self, limit: int = 20) -> Dict[str, Any]:
        return self._api_request("GET", "bff/v1/getLoginHistory", params={"payPayLang": "ja", "limit": str(limit)})

    def get_devices(self) -> Dict[str, Any]:
        return self._api_request("GET", "bff/v1/getDevices", params={"payPayLang": "ja"})

    def get_kyc_status(self) -> Dict[str, Any]:
        return self._api_request("GET", "bff/v1/getKycStatus", params={"payPayLang": "ja"})

    def get_barcode_info(self, url_or_code: str) -> Dict[str, Any]:
        code = url_or_code
        if code.startswith(("http://", "https://")):
            code = code.split("?code=")[-1].split("&")[0] if "?code=" in code else code.rstrip("/").split("/")[-1]
        
        return self._api_request(
            "GET", "bff/v2/getBarcodeInfo",
            params={"code": code, "payPayLang": "ja", "isScannedFromFile": "false"},
        )

    def pay_qr_code(self, url_or_code: str, amount: Optional[int] = None) -> Dict[str, Any]:
        info = self.get_barcode_info(url_or_code)
        payload = info.get("payload", {})
        order_id = payload.get("orderId") or payload.get("preAuthOrderId")
        pay_amount = amount if amount is not None else payload.get("amount")

        if not order_id:
            raise OpPayPayError("QRコードからorderIdを取得できませんでした")

        body: Dict[str, Any] = {
            "requestId": str(uuid.uuid4()),
            "orderId": order_id,
            "currency": "JPY",
        }
        if pay_amount is not None:
            body["amount"] = int(pay_amount)
        
        merchant = payload.get("merchantId")
        if merchant:
            body["merchantId"] = merchant

        return self._api_request("POST", "bff/v2/executePreAuthPayment", json=body)

    def create_p2pcode(self, amount: Optional[int] = None) -> Dict[str, Any]:
        payload = {"amount": amount, "sessionId": str(uuid.uuid4())} if amount else {"amount": None, "sessionId": None}
        return self._api_request("POST", "bff/v1/createP2PCode", json=payload, params={"payPayLang": "ja"})

    def create_paymentcode(self, method: str = "WALLET", method_id: str = "106177237") -> Dict[str, Any]:
        return self._api_request(
            "POST", "bff/v3/createPaymentOneTimeCodeForHome",
            json={
                "paymentMethodType": method,
                "paymentMethodId": method_id,
                "paymentCodeSessionId": str(uuid.uuid4()),
            },
            params={"payPayLang": "ja"},
        )

    def get_payment_methods(self) -> Dict[str, Any]:
        return self._api_request("GET", "bff/v2/getPaymentMethodList", params={"payPayLang": "ja"})

    def get_registered_banks(self) -> Dict[str, Any]:
        return self._api_request("GET", "bff/v1/getRegisteredBanks", params={"payPayLang": "ja"})

    def get_registered_cards(self) -> Dict[str, Any]:
        return self._api_request("GET", "bff/v1/getRegisteredCards", params={"payPayLang": "ja"})

    def get_payout_info(self) -> Dict[str, Any]:
        return self._api_request("GET", "bff/v2/getPayoutDisplayInfo", params={"payPayLang": "ja"})

    def cashout_to_paypaybank(self, amount: int, payout_method_id: Optional[str] = None) -> Dict[str, Any]:
        if not payout_method_id:
            info = self.get_payout_info()
            methods = info.get("payload", {}).get("payoutMethods") or []
            for m in methods:
                name = (m.get("bankName") or m.get("name") or "").lower()
                if "paypay" in name or m.get("isDefault"):
                    payout_method_id = m.get("payoutMethodId") or m.get("id")
                    break
            if not payout_method_id and methods:
                payout_method_id = methods[0].get("payoutMethodId") or methods[0].get("id")
            if not payout_method_id:
                raise OpPayPayError("出金先が見つかりません。銀行口座を登録してください。")

        return self._api_request(
            "POST", "bff/v1/saveBankStandingInstruction",
            json={
                "requestId": str(uuid.uuid4()),
                "payoutMethodId": payout_method_id,
                "amount": int(amount),
            },
            params={"payPayLang": "ja"},
        )

    def get_notifications(self, limit: int = 20) -> Dict[str, Any]:
        return self._api_request("GET", "bff/v1/getNotifications", params={"payPayLang": "ja", "limit": str(limit)})

    def mark_notification_read(self, notification_id: str) -> Dict[str, Any]:
        return self._api_request(
            "POST", "bff/v1/markNotificationRead",
            json={"notificationId": notification_id},
            params={"payPayLang": "ja"},
        )

    def get_campaigns(self) -> Dict[str, Any]:
        return self._api_request("GET", "bff/v1/getCampaigns", params={"payPayLang": "ja"})

    def get_coupons(self) -> Dict[str, Any]:
        return self._api_request("GET", "bff/v1/getCoupons", params={"payPayLang": "ja"})

    def get_bill_info(self, bill_id: str) -> Dict[str, Any]:
        return self._api_request("GET", f"bff/v1/getBillInfo/{bill_id}", params={"payPayLang": "ja"})

    def pay_bill(self, bill_id: str, payment_method_id: str) -> Dict[str, Any]:
        return self._api_request(
            "POST", "bff/v1/payBill",
            json={
                "billId": bill_id,
                "paymentMethodId": payment_method_id,
                "sessionId": str(uuid.uuid4()),
            },
            params={"payPayLang": "ja"},
        )

    def get_gift_voucher_balance(self) -> Dict[str, Any]:
        return self._api_request("GET", "bff/v1/getGiftVoucherBalance", params={"payPayLang": "ja"})

    def get_securities_balance(self) -> Dict[str, Any]:
        return self._api_request("GET", "bff/v1/getSecuritiesBalance", params={"payPayLang": "ja"})

    def _extract_verification_code(self, link_or_code: str) -> str:
        s = link_or_code.strip()
        if "/" not in s and "?" not in s:
            return s
        m = re.search(r"([A-Za-z0-9_-]{10,})/?$", s.split("?", 1)[0])
        if not m:
            raise ValueError(f"verificationCode を抽出できません: {link_or_code!r}")
        return m.group(1)

    def link_check(self, link_or_code: str) -> Dict[str, Any]:
        code = self._extract_verification_code(link_or_code)
        payload = self._web_request(
            "GET", "app/v2/p2p-api/getP2PLinkInfo",
            params={"verificationCode": code},
        )
        payload.setdefault("verificationCode", code)
        return payload

    def link_receive(
        self,
        link_or_code: str,
        password: Optional[str] = None,
        *,
        link_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        code = self._extract_verification_code(link_or_code)
        info = link_info if link_info is not None else self.link_check(code)

        status = info.get("payload", {}).get("orderStatus")
        if status and status != "PENDING":
            raise OpPayPayError(f"リンクは既に処理済みです (status={status})")

        pending = info.get("payload", {}).get("pendingP2PInfo", {})
        if pending.get("isSetPasscode") and password is None:
            raise OpPayPayError("このリンクにはパスワードが必要です")

        message = info.get("payload", {}).get("message", {})
        data = message.get("data", {})

        jst_now = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%dT%H:%M:%S%z")
        body = {
            "verificationCode": code,
            "client_uuid": self.client_uuid,
            "requestAt": jst_now,
            "requestId": data.get("requestId") or str(uuid.uuid4()).upper(),
            "orderId": data.get("orderId") or pending.get("orderId"),
            "senderMessageId": message.get("messageId"),
            "senderChannelUrl": message.get("chatRoomId"),
            "iosMinimumVersion": "3.45.0",
            "androidMinimumVersion": "3.45.0",
        }
        if password is not None:
            body["passcode"] = str(password)

        return self._web_request("POST", "app/v2/p2p-api/acceptP2PSendMoneyLink", json=body)

    def link_reject(
        self,
        link_or_code: str,
        *,
        link_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        code = self._extract_verification_code(link_or_code)
        info = link_info if link_info is not None else self.link_check(code)

        status = info.get("payload", {}).get("orderStatus")
        if status and status != "PENDING":
            raise OpPayPayError(f"リンクは既に処理済みです (status={status})")

        message = info.get("payload", {}).get("message", {})
        data = message.get("data", {})

        jst_now = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%dT%H:%M:%S%z")
        body = {
            "requestAt": jst_now,
            "orderId": data.get("orderId"),
            "verificationCode": code,
            "requestId": str(uuid.uuid4()).upper(),
            "senderMessageId": message.get("messageId"),
            "senderChannelUrl": message.get("chatRoomId"),
            "iosMinimumVersion": "3.45.0",
            "androidMinimumVersion": "3.45.0",
            "client_uuid": self.client_uuid,
        }
        return self._web_request("POST", "app/v2/p2p-api/rejectP2PSendMoneyLink", json=body)

    def get_session_json(self) -> Dict[str, Any]:
        return {
            "phone_number": self.phone,
            "password": self.password,
            "device_uuid": self.device_uuid,
            "client_uuid": self.client_uuid,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
        }


def _extract_error_message(body: Any) -> str:
    if not isinstance(body, dict):
        return str(body)

    if body.get("response_type") == "ErrorResponse":
        info = body.get("result_info", {})
        code = info.get("result_code")
        msg = info.get("result_msg")
        
        if code == "INTERNAL_AUTH_INVALID_GRANT_ERROR":
            return "電話番号またはパスワードが正しくありません。"
        if code == "INTERNAL_AUTH_ACCOUNT_LOCKED_ERROR":
            raise OpPayPayAccountLockedError("アカウントがロックされています。運営にお問い合わせください。")
        if code == "INVALID_AUTH_SEND_OTP_OVER_LIMIT_COUNT_BAD_REQUEST":
            raise OpPayPayRateLimitError("OTP送信回数制限に達しました。時間をおいてください。")
        
        return f"[{code}] {msg}" if code else str(msg)

    header = body.get("header", {})
    result_code = header.get("resultCode")
    result_msg = header.get("resultMessage", "")
    error_detail = body.get("error", {})

    if result_code == "S0000":
        return "Success"

    if result_code == "S0001":
        return "セッションが無効です。再度ログインしてください。"
    
    if result_code == "S9999":
        backend_code = error_detail.get("backendResultCode", "")
        display_error = error_detail.get("displayErrorResponse", {})
        description = display_error.get("description", result_msg)
        
        if backend_code == "P2P_30_SENDER_LIMIT":
            return "送金限度額を超えています。"
        if backend_code == "KYC_INFO_REQUIRED_FOR_PREPAID":
            return "本人確認が必要です。"
        if backend_code == "PAYER_BLACKLIST" or "制限" in description:
            return "セキュリティ上の理由により、ご利用が制限されています。"
        if backend_code == "P2P_RECEIVER_ABNORMALLY_BLOCKING":
            return "送金先のアカウントに制限がかかっているか、詐欺防止のためブロックされました。"
        
        return f"S9999: {description} (Code: {backend_code})"

    if result_code in ("S2205", "S1005"):
        return "残高が不足しています。"

    if result_code == "S5000":
        backend_code = error_detail.get("backendResultCode", "")
        if backend_code == "00400045":
            return "指定されたユーザーが見つかりません。"
        if backend_code == "42007001":
            return "自分自身への送金はできません。"
        return f"S5000: 予期せぬサーバーエラー ({backend_code})"

    return f"[{result_code}] {result_msg}"


def _parse_web_response(resp: curl_requests.Response) -> Dict[str, Any]:
    if resp.status_code == 403:
        raise OpPayPayNetworkError("アクセスが拒否されました (403)。IP制限または地域制限の可能性があります。")
    if resp.status_code == 429:
        raise OpPayPayRateLimitError("レート制限を受けました。")
    
    try:
        body = resp.json()
    except ValueError:
        raise OpPayPayNetworkError(f"JSONパース失敗 (HTTP {resp.status_code}): {resp.text[:200]}")

    msg = _extract_error_message(body)
    if resp.status_code >= 400 or body.get("response_type") == "ErrorResponse":
        raise OpPayPayLoginError(msg)
        
    return body


def _parse_mobile_response(resp: curl_requests.Response) -> Dict[str, Any]:
    if resp.status_code == 429:
        raise OpPayPayRateLimitError("レート制限を受けました。")
    
    try:
        body = resp.json()
    except ValueError:
        raise OpPayPayNetworkError(f"JSONパース失敗 (HTTP {resp.status_code}): {resp.text[:200]}")

    header = body.get("header", {})
    if header.get("resultCode") == "S0001":
        raise OpPayPayBotDetectedError("Bot検知またはセッション切れによりログアウトされました。")
    
    msg = _extract_error_message(body)
    if header.get("resultCode") != "S0000":
        raise OpPayPayError(msg)
        
    return body
