import random
from typing import NamedTuple

class DeviceState(NamedTuple):
    device_acceleration: str
    device_acceleration_2: str
    device_orientation: str
    device_orientation_2: str
    device_rotation: str
    device_rotation_2: str

def generate_device_state() -> DeviceState:
    return DeviceState(
        device_acceleration=f"{random.uniform(-0.1, 0.1):.6f}",
        device_acceleration_2=f"{random.uniform(-0.1, 0.1):.6f}",
        device_orientation=f"{random.uniform(-0.1, 0.1):.6f}",
        device_orientation_2=f"{random.uniform(-0.1, 0.1):.6f}",
        device_rotation=f"{random.uniform(-0.1, 0.1):.6f}",
        device_rotation_2=f"{random.uniform(-0.1, 0.1):.6f}",
    )

def update_header_device_state(headers: dict) -> dict:
    state = generate_device_state()
    headers["Device-Acceleration"] = state.device_acceleration
    headers["Device-Acceleration-2"] = state.device_acceleration_2
    headers["Device-Orientation"] = state.device_orientation
    headers["Device-Orientation-2"] = state.device_orientation_2
    headers["Device-Rotation"] = state.device_rotation
    headers["Device-Rotation-2"] = state.device_rotation_2
    return headers