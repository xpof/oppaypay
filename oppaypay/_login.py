import os
import json
import time
import uuid
import random
import stat
import threading
import logging
from pathlib import Path

from curl_cffi import requests as curl_requests

__version__ = "0.20.0"

log = logging.getLogger("oppaypay")

BASE_URL = "https://app4.paypay.ne.jp"
API_BASE = f"{BASE_URL}/bff/v2"
OAUTH2_BASE = "https://www.paypay.ne.jp/portal/oauth2"

DEVICE = {
    "model": "iPhone 17 Pro",
    "model_id": "iPhone18,1",
    "os": "iOS",
    "os_version": "27.0",
    "app_version": "4.55.0",
    "build": "27A341",
    "locale": "ja_JP",
    "timezone": "Asia/Tokyo",
    "carrier": "KDDI",
    "screen": "1206x2622",
    "scale": "3.0",
}

IMPERSONATE_PROFILE = "safari260_ios"
SESSION_DIR = "~/.oppaypay"
SESSION_FILE = "session.json"

IOS_27_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 27_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/27.0 Mobile/15E148 Safari/604.1"
)


def _uuid4() -> str:
    return str(uuid.uuid4())


def _uuid7() -> str:
    timestamp_ms = int(time.time() * 1000)
    rand_a = random.getrandbits(12)
    rand_b = random.getrandbits(62)

    uuid_int = 0
    uuid_int |= (timestamp_ms & 0xFFFFFFFFFFFF) << 80  
    uuid_int |= 0x7 << 76                                
    uuid_int |= rand_a << 64                             
    uuid_int |= 0b10 << 62                               
    uuid_int |= rand_b                                   

    return str(uuid.UUID(int=uuid_int))


class OppayPayError(Exception):
    pass

class LoginError(OppayPayError):
    pass

class OTPError(LoginError):
    pass

class SessionExpiredError(OppayPayError):
    pass

class BotDetectedError(OppayPayError):
    pass

class EKYCRequiredError(OppayPayError):
    pass

class AccountLockedError(OppayPayError):
    pass

class InsufficientBalanceError(OppayPayError):
    pass

class APIError(OppayPayError):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


def build_headers(access_token: str = None, device_uuid: str = None) -> dict:
    if device_uuid is None:
        device_uuid = _uuid4()

    headers = {
        "User-Agent": IOS_27_UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Content-Type": "application/json; charset=utf-8",
        "X-Device-Model": DEVICE["model"],
        "X-Device-Model-Id": DEVICE["model_id"],
        "X-OS": DEVICE["os"],
        "X-OS-Version": DEVICE["os_version"],
        "X-App-Version": DEVICE["app_version"],
        "X-App-Build": DEVICE["build"],
        "X-Platform": "ios",
        "X-Locale": DEVICE["locale"],
        "X-Timezone": DEVICE["timezone"],
        "X-Carrier": DEVICE["carrier"],
        "X-Screen": DEVICE["screen"],
        "X-Scale": DEVICE["scale"],
        "X-Device-UUID": device_uuid,
        "X-Client-Id": "paypay-mobile",
        "X-Client-Version": __version__,
        "Connection": "keep-alive",
        "DNT": "1",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def _gen_accelerometer():
    return {
        "x": round(random.gauss(0.0, 0.02), 4),
        "y": round(random.gauss(0.0, 0.02), 4),
        "z": round(random.gauss(-1.0, 0.02), 4),
    }

def _gen_gyroscope():
    return {
        "x": round(random.gauss(0.0, 0.005), 5),
        "y": round(random.gauss(0.0, 0.005), 5),
        "z": round(random.gauss(0.0, 0.005), 5),
    }

def _gen_magnetometer():
    return {
        "x": round(random.gauss(20.0, 1.0), 3),
        "y": round(random.gauss(-5.0, 1.0), 3),
        "z": round(random.gauss(40.0, 1.0), 3),
    }

def _gen_touch_events(count=None):
    if count is None:
        count = random.randint(0, 5)
    return [
        {
            "x": round(random.uniform(0, 1206), 1),
            "y": round(random.uniform(0, 2622), 1),
            "pressure": round(random.uniform(0.1, 1.0), 3),
            "timestamp": int(time.time() * 1000) + random.randint(0, 500),
        }
        for _ in range(count)
    ]

def _gen_battery():
    return {
        "level": random.randint(20, 95),
        "charging": random.random() < 0.3,
        "temperature": round(random.uniform(28.0, 36.0), 1),
    }

def generate_motion_payload() -> dict:
    return {
        "accelerometer": _gen_accelerometer(),
        "gyroscope": _gen_gyroscope(),
        "magnetometer": _gen_magnetometer(),
        "touch_events": _gen_touch_events(),
        "battery": _gen_battery(),
        "timestamp": int(time.time() * 1000),
        "uptime": random.randint(3600, 86400 * 3),
    }


def _session_path() -> Path:
    d = Path(os.path.expanduser(SESSION_DIR))
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, stat.S_IRWXU)
    except Exception:
        pass
    return d / SESSION_FILE

def _save_session(data: dict):
    p = _session_path()
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass

def _load_session() -> dict:
    p = _session_path()
    if not p.exists():
        raise SessionExpiredError("セッションファイルが存在しません。")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def _has_session() -> bool:
    return _session_path().exists()


class PayPayClient:
    def __init__(
        self,
        access_token: str = None,
        device_uuid: str = None,
        proxy: str = None,
        enable_sensors: bool = True,
        enable_jitter: bool = True,
    ):
        self.access_token = access_token
        self.device_uuid = device_uuid
        self.enable_sensors = enable_sensors
        self.enable_jitter = enable_jitter
        self.session = curl_requests.Session(
            impersonate=IMPERSONATE_PROFILE,
            proxies={"https": proxy, "http": proxy} if proxy else None,
            timeout=30,
        )
        self._warmup_done = False

    def _apply_jitter(self):
        if self.enable_jitter:
            time.sleep(random.uniform(0.1, 0.8))

    def _inject_sensors(self, payload: dict) -> dict:
        if self.enable_sensors and isinstance(payload, dict):
            payload.setdefault("device_motion", generate_motion_payload())
        return payload

    def _safe_json(self, resp):
        try:
            return resp.json()
        except Exception:
            return {"raw": resp.text}

    def _handle_response(self, resp):
        if resp.status_code == 401:
            body = self._safe_json(resp)
            code = body.get("code", "")
            if code in ("S0001", "S0002"):
                raise BotDetectedError(
                    "Bot検知によりログアウトされました。"
                    "セッションを再取得してください。"
                )
            raise SessionExpiredError("セッションが期限切れです。")

        if resp.status_code == 403:
            body = self._safe_json(resp)
            raise AccountLockedError(
                f"アクセス拒否: {body.get('message', 'アカウントロックの可能性')}"
            )

        if resp.status_code == 428:
            raise EKYCRequiredError(
                "eKYC（本人確認）が完了していません。"
                "PayPay公式アプリで本人確認を完了してください。"
            )

        if resp.status_code >= 400:
            body = self._safe_json(resp)
            raise APIError(
                body.get("code", resp.status_code),
                body.get("message", resp.text[:200]),
            )
        return self._safe_json(resp)

    def warmup(self):
        if self._warmup_done:
            return
        try:
            self.session.get(
                "https://www.paypay.ne.jp/",
                headers=build_headers(self.access_token, self.device_uuid),
            )
            self._warmup_done = True
        except Exception as e:
            log.warning(f"warmup failed: {e}")

    def request(self, method: str, path: str, **kwargs) -> dict:
        if not self._warmup_done:
            self.warmup()
        self._apply_jitter()

        url = path if path.startswith("http") else f"{API_BASE}{path}"
        headers = build_headers(self.access_token, self.device_uuid)
        headers.update(kwargs.pop("headers", {}))

        if "json" in kwargs:
            kwargs["json"] = self._inject_sensors(kwargs["json"])

        resp = self.session.request(method, url, headers=headers, **kwargs)
        return self._handle_response(resp)

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def put(self, path, **kwargs):
        return self.request("PUT", path, **kwargs)

    def delete(self, path, **kwargs):
        return self.request("DELETE", path, **kwargs)


class HumanPatternSimulator:
    ENDPOINTS = [
        "/account/balance",
        "/account/profile",
        "/account/notification",
        "/history/transactions",
        "/chat/rooms",
        "/external/links",
    ]

    def __init__(self, client, interval_range=(30, 180)):
        self.client = client
        self.interval_range = interval_range
        self._stop = threading.Event()
        self._thread = None

    def _run(self):
        log.info("alive simulator started")
        while not self._stop.is_set():
            wait = random.uniform(*self.interval_range)
            if self._stop.wait(wait):
                break
            for _ in range(random.randint(1, 3)):
                ep = random.choice(self.ENDPOINTS)
                try:
                    self.client.get(ep)
                    log.debug(f"alive: GET {ep}")
                except Exception as e:
                    log.debug(f"alive failed: {e}")
                time.sleep(random.uniform(0.5, 3.0))

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        log.info("alive simulator stopped")


def _login(sms: str, password: str, proxy: str = None) -> str:
    """
    仮ログイン。2FA 用のワンタイムリンクを発行する。
    戻り値: pre_id (uuidV4)
    """
    client = PayPayClient(proxy=proxy)
    client.warmup()

    pre_id = _uuid4()              # ← 仮ID は uuidV4
    device_uuid = _uuid4()         # デバイスUUIDも uuidV4

    payload = {
        "login_id": sms,
        "password": password,
        "device_uuid": device_uuid,
        "client_id": "paypay-mobile",
        "client_version": DEVICE["app_version"],
        "device": DEVICE,
        "device_motion": generate_motion_payload(),
        "pre_id": pre_id,
    }

    try:
        resp = client.post(f"{OAUTH2_BASE}/login", json=payload)
    except Exception as e:
        raise LoginError(f"ログイン要求失敗: {e}")

    if resp.get("result", {}).get("status") != "OK":
        code = resp.get("result", {}).get("code", "UNKNOWN")
        raise LoginError(f"ログイン失敗: {code}")

    _save_session({
        "pre_id": pre_id,
        "sms": sms,
        "device_uuid": device_uuid,
        "created_at": int(time.time()),
    })
    return pre_id


def _otp(id: str, verifycode: str, proxy: str = None) -> str:

    if "id=" in verifycode:
        verifycode = verifycode.split("id=")[-1]

    sess = _load_session()
    device_uuid = sess.get("device_uuid")

    client = PayPayClient(device_uuid=device_uuid, proxy=proxy)
    client.warmup()

    payload = {
        "pre_id": id,
        "verify_code": verifycode,
        "device_uuid": device_uuid,
        "device_motion": generate_motion_payload(),
    }

    try:
        resp = client.post(f"{OAUTH2_BASE}/otp", json=payload)
    except Exception as e:
        raise OTPError(f"OTP検証失敗: {e}")

    result = resp.get("result", {})
    if result.get("status") != "OK":
        raise OTPError(f"OTP認証失敗: {result.get('code', 'UNKNOWN')}")

    # サーバーが access_token を返せばそれを採用、
    # 返さない場合は uuidV7 でフォールバック生成
    session_id = result.get("access_token") or _uuid7()   # ← 永続ID は uuidV7

    _save_session({
        "session_id": session_id,
        "device_uuid": device_uuid,
        "sms": sess.get("sms"),
        "created_at": int(time.time()),
        "app_version": DEVICE["app_version"],
        "os_version": DEVICE["os_version"],
    })
    return session_id


def _id(session_id: str = None, proxy: str = None) -> PayPayClient:
    """セッション復帰。保存済み session.json から復元する。"""
    if session_id is None:
        if not _has_session():
            raise LoginError("保存されたセッションがありません。")
        sess = _load_session()
        session_id = sess.get("session_id")
        device_uuid = sess.get("device_uuid")
    else:
        sess = _load_session() if _has_session() else {}
        device_uuid = sess.get("device_uuid")

    if not session_id:
        raise LoginError("session_id が空です。")

    client = PayPayClient(
        access_token=session_id,
        device_uuid=device_uuid,
        proxy=proxy,
    )
    client.warmup()
    return client


# login は関数でありつつ .otp / .id を持つ
login = _login
login.otp = _otp
login.id = _id

# モジュール単体でも otp / id を公開
otp = _otp
id = _id
