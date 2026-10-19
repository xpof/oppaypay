# デバイス偽装（センサー情報やヘッダー）のテストです。




import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oppaypay._sensors import generate_device_state
from oppaypay._core import PayPayCore

def test_device_state():
    print("=== デバイスセンサー情報テスト ===")
    state = generate_device_state()
    print(f"Orientation: {state.device_orientation}")
    print(f"Rotation: {state.device_rotation}")
    print(f"Acceleration: {state.device_acceleration}")
    
    parts = state.device_orientation.split("_")
    assert len(parts) == 3, "デバイスオリエンテーションのフォーマットが不正です"
    for p in parts:
        float(p)
    print("✅ デバイスセンサー情報 成功\n")

def test_core_headers():
    print("=== コアヘッダー生成テスト ===")
    core = PayPayCore()
    headers = core.session.headers
    
    print(f"User-Agent: {headers.get('User-Agent')}")
    print(f"Device-Name: {headers.get('Device-Name')}")
    print(f"Client-OS-Type: {headers.get('Client-OS-Type')}")
    
    assert "PaypayApp" in headers.get('User-Agent', ""), "User-Agentが不正です"
    assert headers.get('Device-Name') == "SCV38", "デバイス名が偽装されていません"
    assert headers.get('Client-OS-Type') == "ANDROID", "OSタイプが不正です"
    print("✅ コアヘッダー生成 成功\n")

if __name__ == "__main__":
    print("--- デバイス偽装・ヘッダー 学習用テスト開始 ---")
    test_device_state()
    test_core_headers()
    print("--- すべてのテストが完了しました ---")