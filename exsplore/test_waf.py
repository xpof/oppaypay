# AWS WAFの突破ロジック（awswaf モジュール）とフィンガープリント生成のテストです。





import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oppaypay._awswaf.verify import CHALLENGE_TYPES, network_bandwidth
from oppaypay._awswaf.fingerprint import get_fp

def test_fingerprint():
    print("=== フィンガープリント生成テスト ===")
    ua = "Mozilla/5.0 (Linux; Android 10; SCV38 Build/QP1A.190711.020; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/132.0.6834.163 Mobile Safari/537.36 jp.pay2.app.android/5.57.0"
    
    checksum, encrypted_fp = get_fp(ua)
    print(f"Checksum: {checksum}")
    print(f"Encrypted FP (first 50 chars): {encrypted_fp[:50]}...")
    
    assert len(checksum) > 0, "Checksumが空です"
    assert "::" in encrypted_fp, "暗号化フォーマットが不正です"
    print("✅ フィンガープリント生成 成功\n")

def test_waf_challenge_types():
    print("=== WAFチャレンジ計算テスト ===")
    challenge_input = "dummy_challenge_input"
    checksum = "ABC12345"
    difficulty = 1
    
    print("Testing NetworkBandwidth...")
    result_bw = network_bandwidth(challenge_input, checksum, difficulty)
    print(f"NetworkBandwidth result (length): {len(result_bw)}")
    assert len(result_bw) > 0, "NetworkBandwidthの結果が空です"
    
    print(f"Registered challenge types: {list(CHALLENGE_TYPES.keys())}")
    assert len(CHALLENGE_TYPES) >= 3, "チャレンジタイプが不足しています"
    print("✅ WAFチャレンジ計算 成功\n")

if __name__ == "__main__":
    print("--- AWS WAF 学習用テスト開始 ---")
    test_fingerprint()
    test_waf_challenge_types()
    print("--- すべてのテストが完了しました ---")