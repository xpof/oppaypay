from ._login import get_core
from .exceptions import OpPayPayError

class _Moneys:
    def all(self, id: str | None = None) -> dict:
        if not id:
            raise OpPayPayError("id は必須です")
        core = get_core(id)
        return core.get_balance()

class _Profile:
    def get(self, id: str | None = None) -> dict:
        if not id:
            raise OpPayPayError("id は必須です")
        core = get_core(id)
        return core.request("get", "https://app4.paypay.ne.jp/bff/v1/getProfile")

moneys = _Moneys()
profile = _Profile()