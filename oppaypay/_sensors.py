import random
import time


def _vector(r1, r2, r3, precision=8):
    v1 = f"{random.uniform(*r1):.{precision}f}"
    v2 = f"{random.uniform(*r2):.{precision}f}"
    v3 = f"{random.uniform(*r3):.{precision}f}"
    return f"{v1}_{v2}_{v3}"


def device_state() -> dict:
    return {
        "Device-Orientation": _vector((2.2, 2.6), (-0.2, -0.05), (-0.05, 0.1)),
        "Device-Orientation-2": _vector((2.0, 2.6), (-0.2, -0.05), (-0.05, 0.2)),
        "Device-Rotation": _vector((-0.8, -0.6), (0.65, 0.8), (-0.12, -0.04)),
        "Device-Rotation-2": _vector((-0.85, -0.4), (0.53, 0.9), (-0.15, -0.03)),
        "Device-Acceleration": _vector((-0.35, 0.0), (-0.01, 0.3), (-0.1, 0.1)),
        "Device-Acceleration-2": _vector((0.01, 0.04), (-0.04, 0.09), (-0.03, 0.1)),
    }


def accelerometer() -> dict:
    return {
        "x": round(random.gauss(0.0, 0.02), 4),
        "y": round(random.gauss(0.0, 0.02), 4),
        "z": round(random.gauss(-1.0, 0.02), 4),
    }


def gyroscope() -> dict:
    return {
        "x": round(random.gauss(0.0, 0.005), 5),
        "y": round(random.gauss(0.0, 0.005), 5),
        "z": round(random.gauss(0.0, 0.005), 5),
    }


def magnetometer() -> dict:
    return {
        "x": round(random.gauss(20.0, 1.0), 3),
        "y": round(random.gauss(-5.0, 1.0), 3),
        "z": round(random.gauss(40.0, 1.0), 3),
    }


def touch_events(count=None) -> list:
    if count is None:
        count = random.randint(0, 5)
    return [
        {
            "x": round(random.uniform(0, 1206), 1),
            "y": round(random.uniform(0, 2622), 1),
            "pressure": round(random.uniform(0.1, 1.0), 3),
            "timestamp": int(time.time() * 1000) + random.randint(0, 500),
        }
        for _ in range(count)
    ]


def battery() -> dict:
    return {
        "level": random.randint(20, 95),
        "charging": random.random() < 0.3,
        "temperature": round(random.uniform(28.0, 36.0), 1),
    }


def motion_payload() -> dict:
    return {
        "accelerometer": accelerometer(),
        "gyroscope": gyroscope(),
        "magnetometer": magnetometer(),
        "touch_events": touch_events(),
        "battery": battery(),
        "timestamp": int(time.time() * 1000),
        "uptime": random.randint(3600, 86400 * 3),
    }


__all__ = [
    "device_state",
    "accelerometer",
    "gyroscope",
    "magnetometer",
    "touch_events",
    "battery",
    "motion_payload",
]