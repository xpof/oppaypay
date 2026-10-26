import time
import uuid
import os

if hasattr(uuid, "uuid7"):
    uuid7 = uuid.uuid7
else:
    def uuid7() -> uuid.UUID:
        ms = int(time.time() * 1000) & ((1 << 48) - 1)
        rand = int.from_bytes(os.urandom(8), 'big') & ((1 << 62) - 1)
        value = (ms << 80) | (0x7 << 76) | (0x2 << 62) | rand
        return uuid.UUID(int=value)