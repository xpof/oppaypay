class OpPayPayError(Exception):
    def __init__(self, response_data: dict | str):
        self.response_data = response_data
        super().__init__(str(response_data))

class OpPayPayLoginError(OpPayPayError): pass
class OpPayPayNetworkError(OpPayPayError): pass
class OpPayPayBotDetectedError(OpPayPayError): pass
class OpPayPayEKYCRequiredError(OpPayPayError): pass
class OpPayPayAccountLockedError(OpPayPayError): pass
class OpPayPayRateLimitError(OpPayPayError): pass
