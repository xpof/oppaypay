from ._core import PayPayCoreBase, Balance
from ._login import PayPayLoginMixin
from ._pay import PayPayPayMixin
from .exceptions import (
    OpPayPayError, OpPayPayLoginError, OpPayPayNetworkError,
    OpPayPayBotDetectedError, OpPayPayEKYCRequiredError,
    OpPayPayAccountLockedError, OpPayPayRateLimitError,
)

class PayPayCore(PayPayCoreBase, PayPayLoginMixin, PayPayPayMixin):
    pass

__version__ = "0.4.2"
__all__ = [
    "PayPayCore", "Balance",
    "OpPayPayError", "OpPayPayLoginError", "OpPayPayNetworkError",
    "OpPayPayBotDetectedError", "OpPayPayEKYCRequiredError",
    "OpPayPayAccountLockedError", "OpPayPayRateLimitError",
]
