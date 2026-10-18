import random
import time
from typing import NamedTuple

def generate_vector(r1, r2, r3, precision=8):
    v1 = f"{random.uniform(*r1):.{precision}f}"
    v2 = f"{random.uniform(*r2):.{precision}f}"
    v3 = f"{random.uniform(*r3):.{precision}f}"
    return f"{v1}_{v2}_{v3}"

class DeviceHeaders(NamedTuple):
    device_orientation: str
    device_orientation_2: str
    device_rotation: str
    device_rotation_2: str
    device_acceleration: str
    device_acceleration_2: str

def generate_device_state() -> DeviceHeaders:
    return DeviceHeaders(
        generate_vector((2.2, 2.6), (-0.2, -0.05), (-0.05, 0.1)),
        generate_vector((2.0, 2.6), (-0.2, -0.05), (-0.05, 0.2)),
        generate_vector((-0.8, -0.6), (0.65, 0.8), (-0.12, -0.04)),
        generate_vector((-0.85, -0.4), (0.53, 0.9), (-0.15, -0.03)),
        generate_vector((-0.35, 0.0), (-0.01, 0.3), (-0.1, 0.1)),
        generate_vector((0.01, 0.04), (-0.04, 0.09), (-0.03, 0.1))
    )

def update_header_device_state(headers: dict):
    state = generate_device_state()
    headers["Device-Orientation"] = state.device_orientation
    headers["Device-Orientation-2"] = state.device_orientation_2
    headers["Device-Rotation"] = state.device_rotation
    headers["Device-Rotation-2"] = state.device_rotation_2
    headers["Device-Acceleration"] = state.device_acceleration
    headers["Device-Acceleration-2"] = state.device_acceleration_2
    return headers

__all__ = ["generate_device_state", "update_header_device_state", "DeviceHeaders"]