import random
import time
import logging
import secrets
import hashlib
from typing import NamedTuple
from uuid import uuid4
from curl_cffi import requests as curl_requests
from ._fingerprint import select_profile
from ._sensors import generate_device_state, update_header_device_state
from ._awswaf import solve_aws_waf_challenge
from ._session import _session_store
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
    money_light: int | None
    all_balance: int | None
    useable_balance: int | None
    points: int | None
    raw: dict

class PayPayCoreBase:
    def __init__(self, phone: str | None = None, password: str | None = None,
                 device_uuid: str | None = None, client_uuid: str | None = None,
                 access_token: str | None = None, refresh_token: str | None = None,
                 proxy: str | None = None, humanize: bool = True,
                 session_id: str | None = None):
        if phone and "-" in phone:
            phone = phone.replace("-", "")
        
        self.phone = phone
        self.password = password
        self.registered_device = device_uuid is not None
        self.device_uuid = device_uuid or str(uuid4())
        self.client_uuid = client_uuid or str(uuid4())
        self.refresh_token = refresh_token
        self.humanize = humanize
        self.session_id = session_id
        
        # ★ 修正1: session_id復元時に self.phone / self.password を更新
        if session_id:
            saved = _session_store.get(session_id)
            if saved:
                self.phone = saved.get("phone", self.phone)
                self.password = saved.get("password", self.password)
                self.device_uuid = saved.get("device_uuid", self.device_uuid)
                self.client_uuid = saved.get("client_uuid", self.client_uuid)
                self.access_token = saved.get("access_token", access_token)
                self.refresh_token = saved.get("refresh_token", self.refresh_token)
                self.registered_device = True
        
        self._mental_focus = secrets.randbelow(1000) / 1000.0
        self._login_headers: dict = {}
        self.access_token: str | None = access_token if not session_id else self.access_token
        self.code_verifier: str | None = None
        
        web_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 26_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/23G71"
        self.session = curl_requests.Session(
            impersonate=select_profile(web_ua),
            proxies={"http": proxy, "https": proxy} if proxy else None,
            timeout=30,
        )
        
        device_state = generate_device_state()
        self.session.headers = {
            "Accept": "*/*", "Accept-Charset": "UTF-8", "Accept-Encoding": "gzip",
            "Client-Mode": "NORMAL", "Client-OS-Release-Version": "26", "Client-OS-Type": "IOS",
            "Client-OS-Version": "26.6", "Client-Type": "PAYPAYAPP", "Client-UUID": self.client_uuid,
            "Client-Version": VERSION, "Connection": "Keep-Alive", "Content-Type": "application/x-www-form-urlencoded",
            "Device-Acceleration": device_state.device_acceleration, "Device-Acceleration-2": device_state.device_acceleration_2,
            "Device-Brand-Name": "Apple", "Device-Hardware-Name": "iPhone", "Device-In-Call": "false",
            "Device-Lock-App-Setting": "false", "Device-Lock-Type": "NONE", "Device-Manufacturer-Name": "Apple",
            "Device-Name": "iPhone 17e", "Device-Orientation": device_state.device_orientation,
            "Device-Orientation-2": device_state.device_orientation_2, "Device-Rotation": device_state.device_rotation,
            "Device-Rotation-2": device_state.device_rotation_2, "Device-UUID": self.device_uuid,
            "Host": "app4.paypay.ne.jp", "Is-Emulator": "false", "Network-Status": "WIFI",
            "System-Locale": "ja", "Timezone": "Asia/Tokyo", "User-Agent": f"PaypayApp/{VERSION} iPhone17e"
        }
        
        if self.access_token:
            self.session.headers["Authorization"] = f"Bearer {self.access_token}"
            self.session.headers["content-type"] = "application/json"
            
        if session_id:
            self.save_session()

    def save_session(self):
        if self.session_id:
            _session_store.save(self.session_id, {
                "phone": self.phone, "password": self.password,
                "device_uuid": self.device_uuid, "client_uuid": self.client_uuid,
                "access_token": self.access_token, "refresh_token": self.refresh_token
            })

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
        max_limit = 1.5 + (secrets.randbelow(300) / 100.0)
        delay = min(delay, max_limit)
        min_limit = secrets.randbelow(50) / 1000.0
        delay = max(delay, min_limit)
        time.sleep(delay)

    def _api_request(self, method: str, url: str, max_retries: int = 3, **kwargs) -> dict:
        last_exception = None
        for attempt in range(max_retries):
            self._human_delay(url)
            try:
                if method.lower() == "get":
                    response = self.session.get(url, **kwargs)
                elif method.lower() == "post":
                    response = self.session.post(url, **kwargs)
                else:
                    raise ValueError("Invalid HTTP method.")
                
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 0))
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
                        if self.refresh_token and attempt < max_retries - 1:
                            try:
                                self.refresh_session()
                                continue
                            except Exception:
                                pass
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

    def _web_request(self, method: str, url: str, headers: dict, allow_redirects: bool = True, max_waf_retries: int = 2, **kwargs) -> curl_requests.Response:
        self._human_delay(url)
        for waf_attempt in range(max_waf_retries):
            if method.lower() == "get":
                response = self.session.get(url, headers=headers, allow_redirects=allow_redirects, **kwargs)
            elif method.lower() == "post":
                response = self.session.post(url, headers=headers, allow_redirects=allow_redirects, **kwargs)
            else:
                raise ValueError("Invalid HTTP method.")
            
            if response.status_code == 202 and 'x-amzn-waf-action' in response.headers:
                log.info(f"AWS WAF challenge detected (attempt {waf_attempt + 1}/{max_waf_retries}). Solving...")
                aws_waf_token = solve_aws_waf_challenge(response.text, headers.get("User-Agent", ""))
                self.session.cookies.set("aws-waf-token", aws_waf_token, domain=".paypay.ne.jp")
                self._human_delay(url)
                continue
            return response
        
        raise OpPayPayNetworkError("WAF challenge resolution failed after multiple attempts")
