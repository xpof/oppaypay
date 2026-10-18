from uuid import uuid4
from ._login import get_core
from .exceptions import OpPayPayError

class _History:
    def get(self, id: str | None = None, size: int = 20, cashback: bool = False) -> dict:
        if not id:
            raise OpPayPayError("id は必須です")
        core = get_core(id)
        return core.request("get", "https://app4.paypay.ne.jp/bff/v1/getHistory", params={"size": size, "cashback": cashback})

class _Profile:
    def get(self, id: str | None = None) -> dict:
        if not id:
            raise OpPayPayError("id は必須です")
        core = get_core(id)
        return core.request("get", "https://app4.paypay.ne.jp/bff/v1/getProfile")

class _Link:
    def check(self, id: str | None = None, url: str = None, web_api: bool = False) -> dict:
        if not url:
            raise OpPayPayError("url は必須です")
        if web_api:
            import requests
            return requests.get(f"https://www.paypay.ne.jp/portal/api/v1/link?url={url}").json()
        core = get_core(id)
        return core.request("get", "https://app4.paypay.ne.jp/bff/v1/linkCheck", params={"url": url})

    def receive(self, id: str | None = None, url: str = None, passcode: str = None) -> dict:
        if not id or not url:
            raise OpPayPayError("id と url は必須です")
        core = get_core(id)
        return core.request("post", "https://app4.paypay.ne.jp/bff/v1/linkReceive", json={"url": url, "passcode": passcode})

    def create(self, id: str | None = None, amount: int = None, passcode: str = None, pochibukuro: bool = False) -> dict:
        if not id or amount is None:
            raise OpPayPayError("id と amount は必須です")
        core = get_core(id)
        return core.request("post", "https://app4.paypay.ne.jp/bff/v1/linkCreate", json={"amount": amount, "passcode": passcode, "pochibukuro": pochibukuro})

class _Send:
    def money(self, id: str | None = None, amount: int = None, receiver_id: str = None) -> dict:
        if not id or amount is None or not receiver_id:
            raise OpPayPayError("id, amount, receiver_id は必須です")
        core = get_core(id)
        return core.request("post", "https://app4.paypay.ne.jp/p2p/v1/sendMoney", json={"amount": amount, "receiverId": receiver_id})

class _P2P:
    def search(self, id: str | None = None, user_id: str = None) -> dict:
        if not id or not user_id:
            raise OpPayPayError("id と user_id は必須です")
        core = get_core(id)
        return core.request("get", "https://app4.paypay.ne.jp/p2p/v1/searchUser", params={"userId": user_id})

    def initialize_chatroom(self, id: str | None = None, external_user_id: str = None) -> dict:
        if not id or not external_user_id:
            raise OpPayPayError("id と external_user_id は必須です")
        core = get_core(id)
        return core.request("post", "https://app4.paypay.ne.jp/p2p/v1/initializeChatroom", json={"externalUserId": external_user_id})

history = _History()
profile = _Profile()
link = _Link()
send = _Send()
p2p = _P2P()