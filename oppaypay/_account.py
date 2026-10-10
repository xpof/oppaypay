from ._login import get_core
from .exceptions import OpPayPayError


class _Moneys:
    def all(self, id: str | None = None) -> int:
        if not id:
            raise OpPayPayError("id は必須です")
        return get_core(id).get_balance().useable_balance

    def money(self, id: str | None = None) -> int | None:
        if not id:
            raise OpPayPayError("id は必須です")
        return get_core(id).get_balance().money

    def money_light(self, id: str | None = None) -> int:
        if not id:
            raise OpPayPayError("id は必須です")
        return get_core(id).get_balance().money_light


class _Account:
    def __init__(self):
        self.moneys = _Moneys()

    def p2p(self, id: str | None = None) -> str:
        if not id:
            raise OpPayPayError("id は必須です")
        response = get_core(id).create_p2pcode()
        url = response["payload"]["p2pCode"]
        if not url.startswith("http"):
            url = f"https://qr.paypay.ne.jp/{url}"
        return url


account = _Account()