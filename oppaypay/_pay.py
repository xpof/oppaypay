from ._login import get_core
from .exceptions import OpPayPayError

class _Money:
    def all(self, id: str | None = None) -> dict:
        if not id:
            raise OpPayPayError("id は必須です")
        core = get_core(id)
        return core.get_balance()

money = _Money()