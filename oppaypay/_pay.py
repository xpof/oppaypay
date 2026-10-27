from uuid import uuid4
from ._core import BASE_URL
from .exceptions import OpPayPayLoginError

class PayPayPayMixin:
    def create_p2pcode(self, amount: int = None):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        payload = {"amount": None, "sessionId": None}
        if amount:
            payload["amount"] = amount
            payload["sessionId"] = str(uuid4())
        return self._api_request("post", f"{BASE_URL}/bff/v1/createP2PCode", json=payload, params={"payPayLang": "ja"})

    def get_barcode_info(self, url: str):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        if url.startswith("https://qr.paypay.ne.jp/"):
            url = url[len("https://qr.paypay.ne.jp/"):]
        url = url.rstrip("/")
        return self._api_request("get", f"{BASE_URL}/bff/v2/getBarcodeInfo?code=https://qr.paypay.ne.jp/{url}", params={"payPayLang": "ja", "isScannedFromFile": "false"})

    def set_money_priority(self, paypay_money: bool = False):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        payload = {"moneyPriority": "MONEY_FIRST" if paypay_money else "MONEY_LITE_FIRST"}
        return self._api_request("post", f"{BASE_URL}/p2p/v1/setMoneyPriority", json=payload, params={"payPayLang": "ja"})

    def pay_qr_code(self, url: str):
        if not self.access_token:
            raise OpPayPayLoginError("まずはログインしてください")
        if url.startswith("https://qr.paypay.ne.jp/"):
            url = url[len("https://qr.paypay.ne.jp/"):]
        url = url.rstrip("/")
        barcode_info = self.get_barcode_info(url)
        dynamic = barcode_info["payload"]["codeInfo"]["dynamicCodeInfo"]
        payload = {
            "requestId": str(uuid4()),
            "merchantId": dynamic["merchantInfo"]["merchantId"],
            "storeId": "",
            "stickerId": "",
            "amount": dynamic["amount"],
            "currency": "JPY",
            "paymentMethodId": barcode_info["payload"]["paymentMethodInfo"]["paymentMethodIdString"],
            "paymentMethodType": "WALLET",
            "agreeSimilarTransactionFlag": False,
            "code": dynamic["code"],
            "merchantOrderId": dynamic["merchantOrderId"],
            "mode": "DYNAMIC_QR"
        }
        return self._api_request("post", f"{BASE_URL}/bff/v2/executePayment", json=payload, params={"payPayLang": "ja"})