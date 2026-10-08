from ._login import get_core
from .exceptions import OpPayPayError


def _create_request_link(session_id: str | None, amount: int | None) -> dict:
    """請求リンク(qr.paypay.ne.jp/...)を生成する"""
    if not session_id:
        raise OpPayPayError("getpayrequestlink(セッションID) は必須です")
    if amount is None or amount <= 0:
        raise OpPayPayError("billed_amount は 1 円以上の整数です")
    core = get_core(session_id)
    response = core.create_p2pcode(amount=amount)
    payload = response["payload"]
    url = payload["p2pCode"]
    if not url.startswith("http"):
        url = f"https://qr.paypay.ne.jp/{url}"
    return {
        "buildid": payload.get("orderId") or payload.get("sessionId"),
        "url": url,
        "raw": response,
    }


def _confirm_payment(buildid: str | None, payer_id: str | None, money_first: bool) -> dict:
    """請求リンクを支払う"""
    if not buildid:
        raise OpPayPayError("buildid(請求リンク) は必須です")
    if not payer_id:
        raise OpPayPayError("getid(支払う側のセッションID) は必須です")
    core = get_core(payer_id)
    return core.pay_request_link(buildid, money_first=money_first)


class _Confirm:
    """支払い完了名前空間"""

    def money(self, buildid: str | None = None, getid: str | None = None) -> dict:
        """PayPayマネーで支払う"""
        return _confirm_payment(buildid, getid, money_first=True)

    def money_light(self, buildid: str | None = None, getid: str | None = None) -> dict:
        """PayPayマネーライトで支払う"""
        return _confirm_payment(buildid, getid, money_first=False)


class _Pay:
    """請求リンク名前空間

    oppaypay.pay.money(getpayrequestlink=..., billed_amount=...)       -> 請求リンク生成
    oppaypay.pay.money_light(getpayrequestlink=..., billed_amount=...) -> 請求リンク生成
    oppaypay.pay.confirm.money(buildid=..., getid=...)                 -> マネーで支払う
    oppaypay.pay.confirm.money_light(buildid=..., getid=...)           -> マネーライトで支払う
    """

    def __init__(self):
        self.confirm = _Confirm()

    def money(self, getpayrequestlink: str | None = None, billed_amount: int | None = None) -> dict:
        return _create_request_link(getpayrequestlink, billed_amount)

    def money_light(self, getpayrequestlink: str | None = None, billed_amount: int | None = None) -> dict:
        return _create_request_link(getpayrequestlink, billed_amount)


pay = _Pay()
