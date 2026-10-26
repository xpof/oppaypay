import json
import random
import string

def generate_client_info():
    return {
        "clientId": "".join(random.choices(string.ascii_lowercase + string.digits, k=32)),
        "clientVersion": "5.57.0",
        "platform": "ANDROID"
    }