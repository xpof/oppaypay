<img width="91" height="89" alt="logo" src="https://github.com/user-attachments/assets/cfafe8d9-4e3d-4975-b39c-ecb920d6e9ec" />
[agehan AI]   :agehan AI:   

# oppaypay v.0.3.0

---

## v0.3.0 の変更点
- **AWS WAFチャレンジ自動解決機能の統合**: `paypy` (paypaypay) のロジックを移植し、`challenge.js` の暗号解析（Scrypt, SHA256 PoW, NetworkBandwidth）をPythonで完全再現。ログイン時のWAFブロックを自動突破します。
- **完全なモバイルアプリ偽装**: Android 10 (API 29) / Galaxy S9 (SCV38) のデバイス情報、加速度・ジャイロセンサー情報、WebViewのUser-Agentをヘッダーに付与。
- **WebGLフィンガープリントの拡張**: AWS WAFのフィンガープリントチェックを通過するため、モバイル向けGPU（Apple A17 Pro, Adreno 740）の情報を追加。
- **多機能APIの統合**: 送金リンクの作成・受取・辞退、送金、QR決済、PayPay銀行への出金、チャットルーム操作など、`paypy` 互換の豊富な機能を追加。
- **TLS/HTTP2フィンガープリント偽装**: `curl_cffi` を採用し、ブラウザ（Chrome/Safari）のTLSハンドシェイクを模倣。

---

PayPay の非公式モバイル API クライアントライブラリです。

本ライブラリは PayPay 公式の提供するものではありません。PayPay 株式会社とは関係がありません。

## 注意事項

- PayPay アプリの内部 API を利用します。非公開のため、予告なく変更・停止される可能性があります。
- 利用にあたっては PayPay の利用規約をご確認ください。アカウントが制限されるリスクがあります。
- 本番運用や金銭取引の自動化への利用は推奨しません。発生した損害について開発者は責任を負いません。
- ログインを3回失敗するとアカウントが一時ロックされます。
- セッションを大量に作るとアカウント凍結の可能性があります。
- 日本国外からはアクセスできません（プロキシの利用が必要です）。

## インストール

```bash
pip install oppaypay
```

## ログイン

### 新規デバイスでログイン（2FA必要）

```python
from oppaypay import login

# 仮ログイン。2FA 用のワンタイムリンクが発行されます。
# AWS WAF チャレンジも自動で解決します。
pre_id = login(sms="08012345678", password="your_password")
print(pre_id)

# 別のデバイスで PayPay アプリに表示されたワンタイムリンクを承認後、
# id= の部分を verifycode として入力します。
session_id = login.otp(id=pre_id, verifycode="TK4602")
print(session_id)
```

### 登録済みデバイスでログイン（2FA不要）

```python
from oppaypay import login

# 以前のログインで取得した device_uuid を指定すると、2FAをスキップできます。
# ※ 現在の実装では login() に device_uuid を直接渡す仕様に調整が必要です。
# セッション復帰 (login.id) を推奨します。
```

### セッションの復帰

```python
from oppaypay import login

login.id(id=session_id)
```

セッション情報は `~/.oppaypay/session.json` に保存され、2回目以降は SMS 認証なしでログインできます。

## 人間パターンシミュレータ

Bot検知を回避するため、バックグラウンドで人間らしい操作パターンを送信します。

```python
from oppaypay import HumanPatternSimulator, get_core

login.id(id=session_id)
core = get_core(session_id)

sim = HumanPatternSimulator(core, interval_range=(30, 180))
sim.start()

# ... アプリ使用中はバックグラウンドで自然なリクエストを送信 ...

sim.stop()
```

## 残高・プロフィール取得

```python
from oppaypay import account, profile

# 残高確認
print(account.moneys.all(id=session_id))          # 利用可能な残高(合計)
print(account.moneys.money(id=session_id))        # PayPayマネー
print(account.moneys.money_light(id=session_id))  # PayPayマネーライト

# プロフィール確認 (v0.3.0 追加)
prof = profile.get(id=session_id)
print(prof.name)
print(prof.external_user_id)
```

## 送金リンク (v0.3.0 追加)

```python
from oppaypay import link

# リンクの確認
info = link.check(id=session_id, url="https://pay.paypay.ne.jp/KT975hvzbH1EulTr")
print(info.amount)

# リンクの受取
link.receive(id=session_id, url="https://pay.paypay.ne.jp/KT975hvzbH1EulTr")

# リンクの作成 (ぽち袋モード)
res = link.create(id=session_id, amount=100, pochibukuro=True)
print(res.link)
```

## 送金・チャット (v0.3.0 追加)

```python
from oppaypay import send, p2p

# ユーザー検索
user = p2p.search(id=session_id, user_id="paypay_id")
print(user.external_user_id)

# チャットルームの初期化
room = p2p.initialize_chatroom(id=session_id, external_user_id=user.external_user_id)

# 送金
send.money(id=session_id, amount=100, receiver_id=user.external_user_id)
```

## QRコード決済・請求リンク

```python
from oppaypay import pay, get_core

# 請求リンクの作成 (自分が受け取る側)
req = pay.money(getpayrequestlink=session_id, billed_amount=1000)
print(req["url"])

# 支払い (自分が支払う側)
pay.confirm.money(buildid=req["url"], getid=payer_session_id)

# QRコード決済 (v0.3.0 追加)
core = get_core(session_id)
result = core.pay_qr_code(url="https://qr.paypay.ne.jp/XXXXX")
print(result.amount)
print(result.merchant_name)
```

## PayPay銀行への出金 (v0.3.0 追加)

```python
from oppaypay import get_core

core = get_core(session_id)
result = core.cashout_to_paypaybank(amount=1000)
print(result.bank_name)
print(result.bank_account_number)
```

## 例外クラス

v0.3.0 では以下の例外クラスを提供します。

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
    OpPayPayRateLimitError,
)

try:
    account.moneys.all(id=session_id)
except OpPayPayBotDetectedError:
    print("Bot検知されました。セッションを再取得してください。")
except OpPayPayRateLimitError:
    print("レート制限に達しました。しばらく待ってください。")
```

## プロキシの使用

```python
from oppaypay import PayPayCore

# セッション復帰時にプロキシを指定
core = PayPayCore(access_token="your_token", proxy="http://host:port")
```

## 既知の問題

- PayPay 側の Bot 検知は継続的にアップデートされるため、v0.3.0 の AWS WAF 突破機能や TLS 偽装も、完全な回避を保証するものではありません。
- `curl_cffi` のバージョンによっては `safari260_ios` などのプロファイルが存在しない場合があります。その場合は自動的に古いプロファイルにフォールバックします。
- AWS WAFの `challenge.js` の仕様が変更された場合、`_awswaf/verify.py` のアップデートが必要になります。

## ライセンス

MIT License

