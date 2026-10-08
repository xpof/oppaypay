from uuid import uuid4

from ._core import PayPayCore
from ._session import store
from ._uuid7 import uuid7
from .exceptions import OpPayPayLoginError

_pending: dict[str, PayPayCore] = {}   # uuidV4 -> 仮ログイン中
_sessions: dict[str, PayPayCore] = {}  # uuidV7 -> ログイン済み


def get_core(session_id: str) -> PayPayCore:
    core = _sessions.get(session_id)
    if core is None:
        raise OpPayPayLoginError("先に login.id(id=...) でログインしてください")
    return core


def _validate(core: PayPayCore) -> None:
    """トークンが生きているか確認する"""
    try:
        core.get_balance()
    except OpPayPayLoginError:
        raise OpPayPayLoginError(
            "セッションが無効です。login(sms=..., password=...) からログインし直してください"
        )


class _Login:
    """ログイン名前空間

    oppaypay.login(sms=..., password=...)      -> 仮ログイン、uuidV4 を返す
    oppaypay.login.otp(id=..., verifycode=...) -> 2FA(OTL)完了、uuidV7 を返す
    oppaypay.login.id(id=...)                 -> 既存セッションでログイン
    """

    def __call__(self, sms: str | None = None, password: str | None = None) -> str:
        if not sms or not password:
            raise OpPayPayLoginError("sms と password は必須です")
        core = PayPayCore(phone=sms, password=password)
        core.login_start()  # 2FA 承認待ちの状態になる
        pre_id = str(uuid4())
        _pending[pre_id] = core
        return pre_id

    def otp(self, id: str | None = None, verifycode: str | None = None) -> str:
        if not id or not verifycode:
            raise OpPayPayLoginError("id と verifycode は必須です")
        core = _pending.pop(id, None)
        if core is None:
            raise OpPayPayLoginError("無効な id です。login() からやり直してください")
        core.login_confirm(verifycode)  # OTL 承認 -> トークン取得

        session_id = str(uuid7())
        store.save(session_id, {
            "access_token": core.access_token,
            "refresh_token": core.refresh_token,
            "device_uuid": core.device_uuid,
            "client_uuid": core.client_uuid,
            "phone": core.phone,
            "password": core.password,
        })
        _sessions[session_id] = core
        return session_id

    def id(self, id: str | None = None) -> bool:
        if not id:
            raise OpPayPayLoginError("id は必須です")
        data = store.get(id)
        if data is None:
            raise OpPayPayLoginError("その id のセッションは存在しません")
        core = PayPayCore(
            access_token=data.get("access_token"),
            device_uuid=data.get("device_uuid"),
            client_uuid=data.get("client_uuid"),
            phone=data.get("phone"),
            password=data.get("password"),
        )
        _validate(core)
        _sessions[id] = core
        return True


login = _Login()
