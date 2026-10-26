class OpPayPayError(Exception):
    def __init__(self, response=None):
        self.response = response
        super().__init__(str(response))

class OpPayPayLoginError(OpPayPayError):
    pass

class OpPayPayNetworkError(OpPayPayError):
    pass

class OpPayPayBotDetectedError(OpPayPayLoginError):
    pass

class OpPayPayEKYCRequiredError(OpPayPayLoginError):
    pass

class OpPayPayAccountLockedError(OpPayPayLoginError):
    pass

class OpPayPayRateLimitError(OpPayPayNetworkError):
    pass