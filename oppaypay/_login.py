import pkce
import logging
import time
import re
import unicodedata
from urllib.parse import parse_qs, urlparse
from ._core import VERSION, BASE_URL, PORTAL_URL
from .exceptions import OpPayPayLoginError

log = logging.getLogger(__name__)

def _parse_sms_code(value: str) -> tuple[str | None, str]:
    if not isinstance(value, str):
        raise OpPayPayLoginError("SMS認証コードを入力してください（例: AG-0918）")
    normalized = unicodedata.normalize("NFKC", value).strip().upper()
    match = re.fullmatch(r"(?:([A-Z]{2})[-\s]?)?(\d{4})", normalized)
    if not match:
        raise OpPayPayLoginError("認証コードの形式が正しくありません。AG-0918 または 0918 の形式で入力してください")
    return match.group(1), match.group(2)

def _extract_oauth_code(redirect_uri: str) -> str:
    code = parse_qs(urlparse(redirect_uri).query).get("code", [None])[0]
    if not code:
        raise OpPayPayLoginError("redirect_uri に認可コードが見つかりませんでした")
    return code

class PayPayLoginMixin:
    def login_start(self):
        if not self.phone:
            raise OpPayPayLoginError("電話番号を入力してください")
        self.access_token = None
        self.code_verifier, self.code_challenge = pkce.generate_pkce_pair(43)
        
        log.debug("Starting PAR request...")
        payload = {
            "clientId": "pay2-mobile-app-client", "clientAppVersion": VERSION, "clientOsVersion": "26.6",
            "clientOsType": "IOS", "redirectUri": "paypay://oauth2/callback", "responseType": "code",
            "state": pkce.generate_code_verifier(43), "codeChallenge": self.code_challenge,
            "codeChallengeMethod": "S256", "scope": "REGULAR", "tokenVersion": "v2", "prompt": "", "uiLocales": "ja"
        }
        response = self._api_request("post", f"{BASE_URL}/bff/v2/oauth2/par?payPayLang=ja", data=payload)
        if response["header"]["resultCode"] != "S0000":
            raise OpPayPayLoginError(response)
        
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Encoding": "gzip, deflate, br, zstd", "Accept-Language": "ja-JP,ja;q=0.9", "Cache-Control": "no-cache",
            "Connection": "keep-alive", "Host": "www.paypay.ne.jp", "is-emulator": "false", "Pragma": "no-cache",
            "sec-ch-ua": '"Not/A)Brand";v="99", "Safari";v="26", "WebKit";v="605"', "sec-ch-ua-mobile": "?1", "sec-ch-ua-platform": '"iOS"',
            "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "none", "Sec-Fetch-User": "?1", "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 26_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/23G71", "X-Requested-With": "jp.ne.paypay.app"
        }
        
        log.debug("Requesting authorize endpoint...")
        params = {"client_id": "pay2-mobile-app-client", "request_uri": response["payload"]["requestUri"]}
        self._web_request("get", f"{PORTAL_URL}/portal/api/v2/oauth2/authorize", headers=headers, params=params, allow_redirects=False)
        
        log.debug("Requesting sign-in page...")
        params = {"client_id": "pay2-mobile-app-client", "mode": "landing"}
        signin_page_response = self._web_request("get", f"{PORTAL_URL}/portal/oauth2/sign-in", headers=headers, params=params)
        if signin_page_response.status_code > 400:
            raise OpPayPayLoginError("サインインページの取得に失敗しました")
        
        headers = {
            "Accept": "application/json, text/plain, */*", "Accept-Encoding": "gzip, deflate, br, zstd", "Accept-Language": "ja-JP,ja;q=0.9",
            "Cache-Control": "no-cache", "Client-Id": "pay2-mobile-app-client", "Client-Type": "PAYPAYAPP", "Connection": "keep-alive",
            "Host": "www.paypay.ne.jp", "Pragma": "no-cache", "Referer": f"{PORTAL_URL}/portal/oauth2/sign-in?client_id=pay2-mobile-app-client&mode=landing",
            "sec-ch-ua": '"Not/A)Brand";v="99", "Safari";v="26", "WebKit";v="605"', "sec-ch-ua-mobile": "?1", "sec-ch-ua-platform": '"iOS"',
            "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 26_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/23G71", "X-Requested-With": "jp.ne.paypay.app"
        }
        
        log.debug("Checking PAR status...")
        par_check_res = self._web_request("get", f"{PORTAL_URL}/portal/api/v2/oauth2/par/check", headers=headers)
        par_check = par_check_res.json()
        if par_check["header"]["resultCode"] != "S0000":
            raise OpPayPayLoginError(par_check)
        
        headers.update({
            "Client-OS-Type": "IOS", "Client-OS-Version": "26.6", "Client-Version": VERSION, "Content-Type": "application/json", "Origin": PORTAL_URL,
        })
        
        log.debug("Sending password for sign-in...")
        payload = {"username": self.phone, "password": self.password, "signInAttemptCount": 1}
        signin_res = self._web_request("post", f"{PORTAL_URL}/portal/api/v2/oauth2/sign-in/password", headers=headers, json=payload)
        signin = signin_res.json()
        if signin["header"]["resultCode"] != "S0000":
            raise OpPayPayLoginError(signin)
        
        if self.registered_device:
            log.debug("Device is registered. Proceeding to token exchange...")
            try:
                uri = signin["payload"]["redirectUrl"].replace("paypay://oauth2/callback?", "").split("&")
            except Exception:
                raise OpPayPayLoginError("登録されていないDevice-UUID、またはリダイレクトURLの解析に失敗")
            self._finish_token_exchange(uri[0].replace("code=", ""))
        else:
            log.debug("Device not registered. Initializing OTP flow...")
            update_res = self._web_request("post", f"{PORTAL_URL}/portal/api/v2/oauth2/extension/code-grant/update", headers=headers, json={})
            if update_res.json()["header"]["resultCode"] != "S0000":
                raise OpPayPayLoginError(update_res.json())
            
            headers["Referer"] = f"{PORTAL_URL}/portal/oauth2/verification-method?client_id=pay2-mobile-app-client&mode=navigation-2fa"
            
            payload = {"params": {"extension_id": "user-main-2fa-v1", "data": {"type": "SELECT_FLOW", "payload": {"flow": "OTP", "sign_in_method": "MOBILE", "base_url": f"{PORTAL_URL}/portal/oauth2/l"}}}}
            update_res2 = self._web_request("post", f"{PORTAL_URL}/portal/api/v2/oauth2/extension/code-grant/update", headers=headers, json=payload)
            
            update_json2 = update_res2.json()
            if update_json2["header"]["resultCode"] != "S0000":
                raise OpPayPayLoginError(update_json2)
            
            payload_data = update_json2.get("payload", {})
            request_data = payload_data.get("request", {})
            data_payload = request_data.get("data", {})
            
            if data_payload.get("type") == "VERIFY_OTP":
                self._otp_prefix = data_payload.get("payload", {}).get("otp_prefix")
                self._login_headers = headers.copy()
                log.info(f"SMS送信完了。認証コード（プレフィックス: {self._otp_prefix}）を入力してください。")
                return 
            
            log.debug("Waiting for the SMS challenge...")
            headers["Referer"] = f"{PORTAL_URL}/portal/oauth2/otl-request?client_id=pay2-mobile-app-client&mode=navigation-2fa"
            self._otp_prefix = None

            max_polling_attempts = 12
            for i in range(max_polling_attempts):
                polling_res = self._web_request("post", f"{PORTAL_URL}/portal/api/v2/oauth2/extension/code-grant/side-channel/next-action-polling", headers=headers, json={"waitUntil": "PT5S"})
                polling_json = polling_res.json()
                log.debug(f"Login polling response (attempt {i+1}/{max_polling_attempts}): {polling_json}")

                if polling_json["header"]["resultCode"] != "S0000":
                    raise OpPayPayLoginError(polling_json)

                payload_data = polling_json.get("payload", {})
                request_data = payload_data.get("request", {})
                data_payload = request_data.get("data", {})

                if data_payload.get("type") == "VERIFY_OTP":
                    self._otp_prefix = data_payload.get("payload", {}).get("otp_prefix")
                    self._login_headers = headers.copy()
                    log.info("SMSに届いた認証コードを login_confirm('AG-0918') のように入力してください。")
                    return

                if data_payload.get("type") == "VERIFY_QR" or data_payload.get("payload", {}).get("previous_interaction") == "COMPLETE_OTL":
                    log.info("OTL has been approved. Calling login_confirm to verify and complete...")
                    self._login_headers = headers.copy()
                    return

                if not payload_data.get("continue", True):
                    log.info("Login polling completed. Waiting for login_confirm...")
                    self._login_headers = headers.copy()
                    return

                time.sleep(1)

            log.warning("OTP challenge is not ready yet. You can still call login_confirm after the SMS arrives.")
            self._login_headers = headers.copy()

    def login_confirm(self, code: str):
        if self.session.headers.get("Authorization"):
            return "already logged in"
        if not self._login_headers:
            raise OpPayPayLoginError("ログインフローが開始されていません。先に login_start を実行してください。")

        if isinstance(code, str) and "https://" in code:
            return self._login_confirm_url(code)

        prefix, otp = _parse_sms_code(code)
        expected_prefix = getattr(self, "_otp_prefix", None)
        if prefix and expected_prefix and prefix != expected_prefix.upper():
            raise OpPayPayLoginError(
                f"認証コードの英字2桁が一致しません。{expected_prefix} から始まるコードを入力してください"
            )

        headers = self._login_headers.copy()
        headers["Referer"] = f"{PORTAL_URL}/portal/oauth2/otl-otp?client_id=pay2-mobile-app-client&mode=navigation-2fa"
        payload = {
            "params": {
                "extension_id": "user-main-2fa-v1",
                "data": {"type": "VERIFY_OTP", "payload": {"otp": otp}},
            }
        }
        log.debug("Verifying SMS OTP (prefix and OTP hidden)")
        update_res = self._web_request("post", f"{PORTAL_URL}/portal/api/v2/oauth2/extension/code-grant/update", headers=headers, json=payload)
        result = update_res.json()
        log.debug(f"VERIFY_OTP response: {result}")

        if result["header"]["resultCode"] != "S0000":
            raise OpPayPayLoginError(result)

        redirect_uri = result.get("payload", {}).get("redirect_uri")
        if not redirect_uri:
            raise OpPayPayLoginError('redirect_uriが見つかりませんでした\n' + str(result))

        self._finish_token_exchange(_extract_oauth_code(redirect_uri))
        self._login_headers = {}
        self._otp_prefix = None
        log.info("SMS認証が完了し、ログインしました。")

    def _login_confirm_url(self, url: str):
        if "id=" in url:
            url = url.split("id=")[-1]
        else:
            raise OpPayPayLoginError("無効な確認URLです")

        headers = self._login_headers.copy()
        headers["Referer"] = f"{PORTAL_URL}/portal/oauth2/l?id={url}&client_id=pay2-mobile-app-client"

        log.debug(f"Sending OTL code for verification: {url[:6]}... (masked)")
        verify_res = self._web_request("post", f"{PORTAL_URL}/portal/api/v2/oauth2/extension/sign-in/2fa/otl/verify", headers=headers, json={"code": url})
        verify_json = verify_res.json()
        log.debug(f"OTL verify response: {verify_json}")

        if verify_json["header"]["resultCode"] != "S0000":
            raise OpPayPayLoginError(verify_json)

        log.debug("Completing OTL flow (code-grant/update)...")
        payload = {"params": {"extension_id": "user-main-2fa-v1", "data": {"type": "COMPLETE_OTL", "payload": None}}}
        update_res = self._web_request("post", f"{PORTAL_URL}/portal/api/v2/oauth2/extension/code-grant/update", headers=headers, json=payload)
        get_uri = update_res.json()
        log.debug(f"COMPLETE_OTL response: {get_uri}")

        if get_uri["header"]["resultCode"] != "S0000":
            raise OpPayPayLoginError(get_uri)

        try:
            redirect_uri = get_uri["payload"]["redirect_uri"]
        except Exception:
            raise OpPayPayLoginError('redirect_uriが見つかりませんでした\n' + str(get_uri))

        self._finish_token_exchange(_extract_oauth_code(redirect_uri))

    def _finish_token_exchange(self, code: str):
        log.debug("Exchanging authorization code for tokens...")
        headers = self.session.headers.copy()
        if "Device-Lock-Type" in headers: del headers["Device-Lock-Type"]
        if "Device-Lock-App-Setting" in headers: del headers["Device-Lock-App-Setting"]
        
        confirm_data = {
            "clientId": "pay2-mobile-app-client", "redirectUri": "paypay://oauth2/callback",
            "code": code, "codeVerifier": self.code_verifier
        }
        get_token = self._api_request("post", f"{BASE_URL}/bff/v2/oauth2/token", headers=headers, data=confirm_data, params={"payPayLang": "ja"})
        if get_token["header"]["resultCode"] != "S0000":
            raise OpPayPayLoginError(get_token)
            
        self.access_token = get_token["payload"]["accessToken"]
        self.refresh_token = get_token["payload"].get("refreshToken")
        self.session.headers["Authorization"] = f"Bearer {self.access_token}"
        self.session.headers["content-type"] = "application/json"
        self.save_session()
        
        log.info("✅ Successfully logged in and saved session.")

    def refresh_session(self) -> bool:
        log.debug("Refreshing access token...")
        if not getattr(self, "refresh_token", None):
            raise OpPayPayLoginError("refresh_token が存在しません。再度ログインしてください。")
            
        headers = self.session.headers.copy()
        if "Device-Lock-Type" in headers: del headers["Device-Lock-Type"]
        if "Device-Lock-App-Setting" in headers: del headers["Device-Lock-App-Setting"]
        
        refresh_data = {
            "clientId": "pay2-mobile-app-client", "grant_type": "refresh_token", "refresh_token": self.refresh_token
        }
        get_token = self._api_request("post", f"{BASE_URL}/bff/v2/oauth2/token", headers=headers, data=refresh_data, params={"payPayLang": "ja"})
        if get_token["header"]["resultCode"] != "S0000":
            raise OpPayPayLoginError(f"トークン更新に失敗しました: {get_token}")
            
        self.access_token = get_token["payload"]["accessToken"]
        self.refresh_token = get_token["payload"].get("refreshToken", self.refresh_token)
        self.session.headers["Authorization"] = f"Bearer {self.access_token}"
        self.session.headers["content-type"] = "application/json"
        self.save_session()
        
        log.info("✅ Successfully refreshed access token.")
        return True
