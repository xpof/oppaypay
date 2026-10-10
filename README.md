# oppaypay v.0.2.0

---

## v0.2.0 の変更点
- curl_cffi 移行：TLS/JA3 および HTTP/2 フィンガープリントを Safari iOS に偽装 やっぱりcurl_cffiのほうが現実的だった
- android 7 / galaxy s9 scv38 からiOS 27 / iPhone 17 Pro への移行　android７はすぐにbot検知されてしまう
- デバイスセンサー生成：加速度・ジャイロ・タッチイベントを模擬送信
- 人間パターンシミュレータ：HumanPatternSimulator で自然なリクエストを送信
- 例外クラス拡充：Bot検知 / eKYC未完了 / アカウントロック / レート制限を明示的に検出

---

PayPay の非公式モバイル API クライアントライブラリです。
内部実装は [PayPaython-mobile](https://github.com/taka-4602/PayPaython-mobile) をベースにしています。

本ライブラリは PayPay 公式の提供するものではありません。PayPay 株式会社とは関係がありません。

## 注意事項

- PayPay アプリの内部 API を利用します。非公開のため、予告なく変更・停止される可能性があります。
- 利用にあたっては PayPay の利用規約をご確認ください。アカウントが制限されるリスクがあります。
- 本番運用や金銭取引の自動化への利用は推奨しません。発生した損害について開発者は責任を負いません。
- ログイン情報・セッショントークンは `~/.oppaypay/session.json` に保存されます。ファイルの取り扱いに注意してください。
- 日本国外からはアクセスできません（プロキシの利用が必要です）。 [日本国内の無料プロキシリスト](https://github.com/xpof/oppaypay/blob/main/Just/japan-proxies.txt)

## インストール

```bash
pip install oppaypay
```

## Let`s go

## 新規ログイン

```python
import oppaypay

# 仮ログイン。2FA 用のワンタイムリンクが発行されます。
# 戻り値は uuidV4 (pre_id)
pre_id = oppaypay.login(sms="08012345678", password="your_password")
print(pre_id)  # uuidV4 (仮ID)

# 別のデバイスで PayPay アプリに表示されたワンタイムリンクを承認後、
# id= の部分を verifycode として入力します。
# 戻り値は uuidV7 (session_id)
session_id = oppaypay.login.otp(id=pre_id, verifycode="TK4602")
print(session_id)  # uuidV7 (永続セッションID)
```

※ SMS の 4桁 OTP は廃止されました。現在の 2FA は
`https://www.paypay.ne.jp/portal/oauth2/l?id=XXXX` 形式の
ワンタイムリンク承認方式です。`verifycode` には URL 全体または `XXXX` 部分を入れます。

### セッションの復帰

```python
oppaypay.login.id(id=session_id)
```

セッション情報は `~/.oppaypay/session.json` に保存され、
2回目以降は SMS 認証なしでログインできます。

## 人間パターンシミュレータ

Bot検知を回避するため、バックグラウンドで人間らしい操作パターンを送信します。

```python
from oppaypay import HumanPatternSimulator

oppaypay.login.id(id=session_id)
core = oppaypay.get_core(session_id)

sim = HumanPatternSimulator(core, interval_range=(30, 180))
sim.start()

# ... アプリ使用中はバックグラウンドで自然なリクエストを送信 ...

sim.stop()
```

`interval_range` はリクエスト間隔の範囲（秒）です。デフォルトは `(30, 180)`。

## 請求リンクの作成

```python
# 請求リンク (https://qr.paypay.ne.jp/...) を生成
req = oppaypay.pay.money(getpayrequestlink=session_id, billed_amount=1000)
print(req["url"])     # https://qr.paypay.ne.jp/...
print(req["buildid"]) # 取引番号

req = oppaypay.pay.money_light(getpayrequestlink=session_id, billed_amount=500)
```

※ 請求リンクの生成自体は残高の種類に依存しません。
マネー / マネーライトの区別は支払い側で行われます。

## 支払い

```python
# PayPayマネーで支払う
oppaypay.pay.confirm.money(buildid=req["url"], getid=payer_session_id)

# PayPayマネーライトで支払う
oppaypay.pay.confirm.money_light(buildid=req["url"], getid=payer_session_id)
```

`buildid` には請求リンクの URL または `https://qr.paypay.ne.jp/` の後ろの部分を指定します。
`getid` は支払う側のセッション ID です。

## 残高の確認

```python
oppaypay.account.moneys.all(id=session_id)          # 利用可能な残高(合計)
oppaypay.account.moneys.money(id=session_id)        # PayPayマネー
oppaypay.account.moneys.money_light(id=session_id)  # PayPayマネーライト
```

## 友だち登録用 URL の生成

```python
url = oppaypay.account.p2p(id=session_id)
print(url)  # https://qr.paypay.ne.jp/...
```

## 例外クラス

v0.2.0 では以下の例外クラスを提供します。

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
    oppaypay.account.moneys.all(id=session_id)
except OpPayPayBotDetectedError:
    print("Bot検知されました。セッションを再取得してください。")
except OpPayPayEKYCRequiredError:
    print("eKYCを完了してください。")
except OpPayPayAccountLockedError:
    print("アカウントがロックされています。")
except OpPayPayRateLimitError:
    print("レート制限に達しました。しばらく待ってください。")
```

## その他

```python
from oppaypay import get_core

core = get_core(session_id)
core.alive()  # Bot検知対策の無駄リクエストを手動で送る
```

通常は `HumanPatternSimulator` を使うことを推奨します。

## 既知の問題

- 2025年11月以降、PayPay 側の Bot 検知強化により新規ログインが失敗する場合があります。
  この場合、PayPay 公式アプリでログインし、アクセストークンを取得して
  `~/.oppaypay/session.json` に登録する運用が必要になります。
- v0.2.0 では curl_cffi による TLS/HTTP2 偽装と iOS 27 偽装を実装していますが、
  PayPay 側の Bot 検知は継続的にアップデートされるため、
  完全な回避を保証するものではありません。
- `curl_cffi` のバージョンによっては `safari260_ios` プロファイルが存在しない場合があります。
  その場合は自動的に古い Safari iOS プロファイルにフォールバックします。

## 追記部分の差分まとめ

| セクション | 操作 | 内容 |
|---|---|---|
| バージョン表記 | 更新 | `v0.1.0` → `v0.2.0` |
| **v0.2.0 の変更点** | **新規追加** | curl_cffi / iOS 27 / センサー / シミュレータ / 例外 / UUID分離 |
| **人間パターンシミュレータ** | **新規追加** | `HumanPatternSimulator` の使用例 |
| **例外クラス** | **新規追加** | 7つの例外クラスの説明と使用例 |
| その他 | 更新 | `core.alive()` の手動呼び出し例、`HumanPatternSimulator` 推奨 |
| 既知の問題 | 更新 | v0.2.0 の対策と curl_cffi フォールバックの注記 |


  

## ライセンス

MIT License
