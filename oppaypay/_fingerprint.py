import random
from curl_cffi.requests import BrowserType

_profiles = [
    BrowserType.chrome,
    BrowserType.chrome100,
    BrowserType.chrome101,
    BrowserType.chrome102,
    BrowserType.chrome103,
    BrowserType.chrome104,
    BrowserType.chrome105,
    BrowserType.chrome106,
    BrowserType.chrome107,
    BrowserType.chrome108,
    BrowserType.chrome109,
    BrowserType.chrome110,
    BrowserType.chrome111,
    BrowserType.chrome112,
    BrowserType.chrome113,
    BrowserType.chrome114,
    BrowserType.chrome115,
    BrowserType.chrome116,
    BrowserType.chrome117,
    BrowserType.chrome118,
    BrowserType.chrome119,
    BrowserType.chrome120,
    BrowserType.chrome140,

]

android_17_user_agent = "Mozilla/5.0 (Linux; Android 10; SCV38 Build/QP1A.190711.020; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/132.0.6834.163 Mobile Safari/537.36 jp.pay2.app.android/5.57.0"

def select_profile():
    return random.choice(_profiles)