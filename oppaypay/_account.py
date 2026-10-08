from ._login import get_core
from .exceptions import OpPayPayError


class _Moneys:
    """残高名前空間"""

    def all(self, id: str | None = None) -> int:
        """利用可能な残高の合計を返す"""
        if not id:
            raise OpPayPayError("id は必須です")
        return get_core(id).get_balance().useable_balance

    def money(self, id: str | None = None) -> int | None:
        """利用可能な PayPayマネー の残高を返す"""
        if not id:
            raise OpPayPayError("id は必須です")
        return get_core(id).get_balance().money

    def money_light(self, id: str | None = None) -> int:
        """利用可能な PayPayマネーライト の残高を返す"""
        if not id:
            raise OpPayPayError("id は必須です")
        return get_core(id).get_balance().money_light


class _Account:
    """アカウント名前空間"""

    def __init__(self):
        self.moneys = _Moneys()

    def p2p(self, id: str | None = None) -> str:
        """友だち登録用の URL を生成する"""
        if not id:
            raise OpPayPayError("id は必須です")
        response = get_core(id).create_p2pcode()
        url = response["payload"]["p2pCode"]
        if not url.startswith("http"):
            url = f"https://qr.paypay.ne.jp/{url}"
        return url


account = _Account()
