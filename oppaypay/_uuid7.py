import time
import uuid

if hasattr(uuid, "uuid7"):
    uuid7 = uuid.uuid7
else:
    def uuid7() -> uuid.UUID:
        """RFC 9562 UUIDv7 (Python 3.13 以前向けの簡易実装)"""
        ms = int(time.time() * 1000) & ((1 << 48) - 1)
        rand = int.from_bytes(uuid.uuid4().bytes[6:], "big")
        value = (ms << 80) | (0x7 << 76) | (rand & ((1 << 76) - 1))
        return uuid.UUID(int=value)
