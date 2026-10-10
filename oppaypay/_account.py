
__all__ = ["_Account", "_Moneys"]


class _Moneys:

    def __init__(self, client):
        self.client = client

    def all(self, id: str):

        return self.client.get("/account/moneys/all")

    def money(self, id: str):

        return self.client.get("/account/moneys/money")

    def money_light(self, id: str):

        return self.client.get("/account/moneys/money_light")


class _Account:

    def __init__(self, client):
        self.client = client
        self.moneys = _Moneys(client)

    def p2p(self, id: str) -> str:

        resp = self.client.get("/account/p2p/link")
        return resp.get("url", "")
