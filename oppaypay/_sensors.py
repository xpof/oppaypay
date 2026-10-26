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
    acc_x = round(random.uniform(-0.1, 0.1), 6)
    acc_y = round(random.uniform(9.7, 9.9), 6)
    acc_z = round(random.uniform(-0.1, 0.1), 6)
    
    ori_alpha = round(random.uniform(0, 360), 2)
    ori_beta = round(random.uniform(-10, 10), 2)
    ori_gamma = round(random.uniform(-10, 10), 2)
    
    rot_alpha = round(random.uniform(0, 360), 2)
    rot_beta = round(random.uniform(-10, 10), 2)
    rot_gamma = round(random.uniform(-10, 10), 2)

    return DeviceState(
        device_acceleration=f"{acc_x},{acc_y},{acc_z}",
        device_acceleration_2=f"{acc_x},{acc_y},{acc_z}",
        device_orientation=f"{ori_alpha},{ori_beta},{ori_gamma}",
        device_orientation_2=f"{ori_alpha},{ori_beta},{ori_gamma}",
        device_rotation=f"{rot_alpha},{rot_beta},{rot_gamma}",
        device_rotation_2=f"{rot_alpha},{rot_beta},{rot_gamma}"
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