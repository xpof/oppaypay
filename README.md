<img width="91" height="89" alt="logo" src="https://github.com/user-attachments/assets/cfafe8d9-4e3d-4975-b39c-ecb920d6e9ec" />  

# oppaypay v.0.4.3

---

### v0.4.3 の変更点
- **API の刷新**: `PayPayCore` クラスベースのオブジェクト指向設計へ完全移行。
- **ログインフローの分離**: `login_otp()`（SMSコード）と `login_otl()`（URL承認）を明確に使い分け可能に。
- **残高取得の拡張**: PayPayポイント、PayPay銀行、PayPay証券、ギフト券残高の取得に対応。
- **WAF ソルバーの強化**: TLS フィンガープリントの整合性確保、`gokuProps` の動的鍵更新、フォールバック処理の実装。
- **センサー生成の高度化**: AR(1) モデルによる加速度・ジャイロセンサーの模擬生成。
- **20以上の新機能追加**: P2P送金、チャージ、出金、入出金明細、通知管理、キャンペーン取得など。

---

PayPay の非公式モバイル API クライアントライブラリです。
内部実装は [PayPaython-mobile](https://github.com/taka-4602/PayPaython-mobile) をベースにしています。
本ライブラリは PayPay 公式の提供するものではありません。PayPay 株式会社とは関係がありません。

### 注意事項
- PayPay アプリの内部 API を利用します。非公開のため、予告なく変更・停止される可能性があります。
- 利用にあたっては PayPay の利用規約をご確認ください。アカウントが制限されるリスクがあります。
- 本番運用や金銭取引の自動化への利用は推奨しません。発生した損害について開発者は責任を負いません。
- ログイン情報・セッショントークンは `paypay_session.json` に保存されます。ファイルの取り扱いに注意してください。
- 日本国外からはアクセスできません（プロキシの利用が必要です）。

### インストール
```bash
pip install oppaypay
```

### Let's go
### 新規ログイン（OTP方式：SMSコード）
```python
from oppaypay import PayPayCore

core = PayPayCore(
    phone="08012345678",
    password="your_password",
    humanize=False, # テスト時は待機時間を短縮
)

# 1. パスワード認証まで実行
core.login_start()

# 2. SMSに届いたコード（例: AG-0918）を入力して認証完了
core.login_otp("AG-0918")

print(f"ログイン成功! access_token: {core.access_token[:20]}...")
```

### 新規ログイン（OTL方式：URL承認）
```python
from oppaypay import PayPayCore

core = PayPayCore(
    phone="08012345678",
    password="your_password",
)

# 1. パスワード認証まで実行
core.login_start()

# 2. URL承認フローを開始（プログラムが承認を自動待機）
# この間にスマホでSMSのURLを開き、QRをスキャンして承認する
core.login_otl()

print(f"ログイン成功! access_token: {core.access_token[:20]}...")
```

### セッションの復帰
2回目以降は、保存された device_uuid を指定することで 2FA をスキップできます。
```python
from oppaypay import PayPayCore

# 初回ログイン時に保存された device_uuid を指定
core = PayPayCore(
    phone="08012345678",
    password="your_password",
    device_uuid="12fc74c8-...", 
)

# 2FA なしで即座にログイン完了
core.login_start()
```

---

### 残高の確認
v0.4.3 から PayPayポイント、銀行、証券、ギフト券残高も取得可能です。
```python
balance = core.get_balance()

print(f"PayPayマネー: {balance.money} 円")
print(f"PayPayマネーライト: {balance.money_light} 円")
print(f"PayPayポイント: {balance.points} pt")
print(f"PayPay銀行: {balance.bank_balance} 円")
print(f"PayPay証券: {balance.securities_balance} 円")
print(f"ギフト券: {balance.gift_voucher_balance} 円")
print(f"合計残高: {balance.all_balance} 円")
```
---
### 追加機能（新API）
#### P2P送金
```python
# 電話番号宛に送金
core.send_money(phone="09012345678", amount=1000, message="ご飯代")
```

#### チャージ・出金
```python
# クレジットカードからチャージ
core.charge_money(amount=5000, payment_method_id="card_xxx")

# 銀行口座へ出金
core.withdraw_money(amount=3000, bank_account_id="bank_xxx")
```

#### 履歴・通知
```python
# 入出金明細
history = core.get_transaction_history(limit=10)

# 通知一覧
notifications = core.get_notifications(limit=20)

# 通知を既読にする
core.mark_notification_read(notification_id="notif_xxx")
```

#### その他
```python
# アカウントプロフィール取得
profile = core.get_profile()

# 本人確認（eKYC）ステータス
kyc = core.get_kyc_status()

# 登録デバイス一覧
devices = core.get_devices()
```

---

## 人間パターンシミュレータ
Bot検知を回避するため、バックグラウンドで人間らしい操作パターンを送信します。
```python
from oppaypay._alive import simulate_human_behavior

# ログイン後、自然なリクエストパターンをシミュレート
simulate_human_behavior(core)
```

---
### 例外クラス
v0.4.3 では以下の例外クラスを提供します。

| 例外クラス | 説明 |
|---|---|
| `OpPayPayError` | 汎用エラー |
| `OpPayPayLoginError` | ログイン失敗・トークン失効・セッション無効 |
| `OpPayPayNetworkError` | ネットワークエラー・レスポンスパース失敗 |
| `OpPayPayBotDetectedError` | Bot検知によるログアウト（S0001/S0002） |
| `OpPayPayEKYCRequiredError` | eKYC（本人確認）未完了 |
| `OpPayPayAccountLockedError` | アカウント一時ロック |
| `OpPayPayRateLimitError` | レート制限超過 |

```python
from oppaypay import (
    OpPayPayBotDetectedError,
    OpPayPayEKYCRequiredError,
    OpPayPayAccountLockedError,
    OpPayPayRateLimitError,
)

try:
    balance = core.get_balance()
except OpPayPayBotDetectedError:
    print("Bot検知されました。セッションを再取得してください。")
except OpPayPayEKYCRequiredError:
    print("eKYCを完了してください。")
except OpPayPayAccountLockedError:
    print("アカウントがロックされています。")
except OpPayPayRateLimitError:
    print("レート制限に達しました。しばらく待ってください。")
```

---

### 既知の問題
- 2026年以降、PayPay 側の Bot 検知強化により新規ログインが失敗する場合があります。この場合、PayPay 公式アプリでログインし、アクセストークンを取得して運用する必要があります。
- `curl_cffi` のバージョンによっては `safari_ios` プロファイルが存在しない場合があります。その場合は自動的に古いプロファイルにフォールバックしますが、最新版（0.16以上）の利用を推奨します。
- OTL（URL承認）方式は、PCブラウザからの直接アクセスが制限されているため、初回認証はスマホでのQRスキャンが必要です。

---

### ライセンス
MIT License
