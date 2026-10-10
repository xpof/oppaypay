from ._login import (
    login, otp, id,
    PayPayClient, HumanPatternSimulator,
    build_headers, generate_motion_payload,
    _uuid4, _uuid7,
    OppayPayError, LoginError, OTPError,
    SessionExpiredError, BotDetectedError,
    EKYCRequiredError, AccountLockedError,
    InsufficientBalanceError, APIError,
)
from ._pay import _Pay
from ._account import _Account

__version__ = "0.20.0"

_client = None
_pay = None
_account = None


def _ensure_client():
    global _client, _pay, _account
    if _client is None:
        _client = id()  
        _pay = _Pay(_client)
        _account = _Account(_client)
    return _client


class _PayProxy:
    def __getattr__(self, name):
        _ensure_client()
        return getattr(_pay, name)


class _AccountProxy:
    def __getattr__(self, name):
        _ensure_client()
        return getattr(_account, name)


pay = _PayProxy()
account = _AccountProxy()

__all__ = [
    "login", "otp", "id",
    "pay", "account",
    "PayPayClient", "HumanPatternSimulator",
    "OppayPayError", "LoginError", "OTPError",
    "SessionExpiredError", "BotDetectedError",
    "EKYCRequiredError", "AccountLockedError",
    "InsufficientBalanceError", "APIError",
    "build_headers", "generate_motion_payload",
]
