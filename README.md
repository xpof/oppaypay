# oppaypay

PayPay の非公式モバイル API クライアントライブラリです。
内部実装は [PayPaython-mobile](https://github.com/taka-4602/PayPaython-mobile) をベースにしています。

本ライブラリは PayPay 公式の提供するものではありません。PayPay 株式会社とは関係がありません。

## 注意事項

- PayPay アプリの内部 API を利用します。非公開のため、予告なく変更・停止される可能性があります。
- 利用にあたっては PayPay の利用規約をご確認ください。アカウントが制限されるリスクがあります。
- 本番運用や金銭取引の自動化への利用は推奨しません。発生した損害について開発者は責任を負いません。
- ログイン情報・セッショントークンは `~/.oppaypay/session.json` に保存されます。ファイルの取り扱いに注意してください。
- 日本国外からはアクセスできません（プロキシの利用が必要です）。 [日本国内の無料プロキシリスト ※使えなくなってるかもです](https://github.com/xpof/oppaypay/blob/main/Just/japan-proxies.txt)

## インストール

```bash
pip install oppaypay
```

## Let`s go

### 新規ログイン

```python
import oppaypay

# 仮ログイン。2FA 用のワンタイムリンクが発行されます。
pre_id = oppaypay.login(sms="08012345678", password="your_password")
print(pre_id)  # uuidV4 (仮ID)

# 別のデバイスで PayPay アプリに表示されたワンタイムリンクを承認後、
# id= の部分を verifycode として入力します。
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

## その他

```python
from oppaypay import login
core = login.__self__  # noqa (内部アクセスの例)
# セッションに紐づく内部クライアント経由で alive() (Bot検知対策の無駄リクエスト) を送る
# などの高度な利用も可能です
```

## 既知の問題

- 2025年11月以降、PayPay 側の Bot 検知強化により新規ログインが失敗する場合があります。
  この場合、PayPay 公式アプリでログインし、アクセストークンを取得して
  `~/.oppaypay/session.json` に登録する運用が必要になります。

## ライセンス

MIT License
