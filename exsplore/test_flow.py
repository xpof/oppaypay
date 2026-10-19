# ログインからセッション復帰までのフローをシミュレートするテストです（実際のアカウント情報が必要です）。







import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oppaypay import login, get_core
from oppaypay.exceptions import OpPayPayLoginError

# テスト用のアカウント情報を入力してください
TEST_PHONE = "08012345678"
TEST_PASSWORD = "your_password"

def test_login_flow():
    print("=== ログインフローテスト ===")
    try:
        print(f"電話番号: {TEST_PHONE} で仮ログインを開始...")
        pre_id = login(sms=TEST_PHONE, password=TEST_PASSWORD)
        print(f"仮ログイン成功。pre_id: {pre_id}")
        
        print("\n⚠️ 実際のログインには、PayPayアプリでのワンタイムリンク承認とOTPコードの入力が必要です。")
        print("以下のコードのコメントアウトを外して実行してください。\n")
        
        # verify_code = input("OTPコードを入力してください: ")
        # session_id = login.otp(id=pre_id, verifycode=verify_code)
        # print(f"ログイン成功！ session_id: {session_id}")
        
        # core = get_core(session_id)
        # balance = core.get_balance()
        # print(f"残高: {balance.useable_balance} 円")
        
    except OpPayPayLoginError as e:
        print(f"ログインエラー: {e}")
    except Exception as e:
        print(f"予期しないエラー: {e}")

if __name__ == "__main__":
    print("--- ログインフロー 学習用テスト開始 ---")
    test_login_flow()