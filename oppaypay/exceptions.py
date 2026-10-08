class OpPayPayError(Exception):
    """oppaypay の汎用エラー"""


class OpPayPayLoginError(OpPayPayError):
    """ログイン失敗・トークン失効・セッション無効"""


class OpPayPayNetworkError(OpPayPayError):
    """ネットワークエラーやレスポンスパース失敗"""
