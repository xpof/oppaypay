class OpPayPayError(Exception):
    pass


class OpPayPayLoginError(OpPayPayError):
    pass


class OpPayPayNetworkError(OpPayPayError):
    pass


class OpPayPayBotDetectedError(OpPayPayLoginError):
    pass


class OpPayPayEKYCRequiredError(OpPayPayError):
    pass


class OpPayPayAccountLockedError(OpPayPayLoginError):
    pass


class OpPayPayRateLimitError(OpPayPayError):
    pass


__all__ = [
    "OpPayPayError",
    "OpPayPayLoginError",
    "OpPayPayNetworkError",
    "OpPayPayBotDetectedError",
    "OpPayPayEKYCRequiredError",
    "OpPayPayAccountLockedError",
    "OpPayPayRateLimitError",
]