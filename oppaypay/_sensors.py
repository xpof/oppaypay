import random
from typing import NamedTuple

class DeviceState(NamedTuple):
    device_acceleration: str
    device_acceleration_2: str
    device_orientation: str
    device_orientation_2: str
    device_rotation: str
    device_rotation_2: str

class SensorState:
    def __init__(self):
        self.accel = [0.0, 9.8, 0.0]
        self.gyro = [0.0, 0.0, 0.0]
        self.orientation = [0.0, 0.0]

    def step(self):
        noise = lambda s: random.gauss(0, s)
        self.accel[0] = 0.9 * self.accel[0] + noise(0.05)
        self.accel[1] = 9.8 + 0.9 * (self.accel[1] - 9.8) + noise(0.1)
        self.accel[2] = 0.9 * self.accel[2] + noise(0.05)
        self.gyro[0] = 0.95 * self.gyro[0] + noise(0.02)
        self.gyro[1] = 0.95 * self.gyro[1] + noise(0.02)
        self.gyro[2] = 0.95 * self.gyro[2] + noise(0.02)
        self.orientation[0] = 0.9 * self.orientation[0] + noise(0.03)
        self.orientation[1] = 0.9 * self.orientation[1] + noise(0.03)

_sensor_state = SensorState()

def generate_device_state() -> DeviceState:
    _sensor_state.step()
    return DeviceState(
        device_acceleration=f"{_sensor_state.accel[0]:.6f}",
        device_acceleration_2=f"{_sensor_state.accel[1]:.6f}",
        device_orientation=f"{_sensor_state.orientation[0]:.6f}",
        device_orientation_2=f"{_sensor_state.orientation[1]:.6f}",
        device_rotation=f"{_sensor_state.gyro[0]:.6f}",
        device_rotation_2=f"{_sensor_state.gyro[1]:.6f}",
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
