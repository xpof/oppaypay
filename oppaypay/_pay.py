class _Confirm:
    def __init__(self, client):
        self.client = client

    def money(self, buildid: str, getid: str):
        if buildid.startswith("https://qr.paypay.ne.jp/"):
            buildid = buildid.split("/")[-1]
        return self.client.post(
            "/pay/confirm",
            json={
                "build_id": buildid,
                "payer_session_id": getid,
                "payment_method": "MONEY",
            },
        )

    def money_light(self, buildid: str, getid: str):
        if buildid.startswith("https://qr.paypay.ne.jp/"):
            buildid = buildid.split("/")[-1]
        return self.client.post(
            "/pay/confirm",
            json={
                "build_id": buildid,
                "payer_session_id": getid,
                "payment_method": "MONEY_LIGHT",
            },
        )


class _Pay:
    def __init__(self, client):
        self.client = client
        self.confirm = _Confirm(client)

    def money(self, getpayrequestlink: str, billed_amount: int):
        return self.client.post(
            "/pay/request",
            json={
                "getpay_request_link": getpayrequestlink,
                "billed_amount": billed_amount,
                "payment_method": "MONEY",
            },
        )

    def money_light(self, getpayrequestlink: str, billed_amount: int):
        return self.client.post(
            "/pay/request",
            json={
                "getpay_request_link": getpayrequestlink,
                "billed_amount": billed_amount,
                "payment_method": "MONEY_LIGHT",
            },
        )
