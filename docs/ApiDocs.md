

\# `oppaypay` API ドキュメント (Web版)



このモジュールは、PayPayのWeb版ポータル (`www.paypay.ne.jp/app`) のAPIを介して、OTP（ワンタイムパスワード）認証によるログインと、限定されたAPI操作を実現します。



> \*\*⚠️ 重要\*\*: Web版APIはモバイルアプリ版 (`app4.paypay.ne.jp`) と比べて機能が制限されています。直接送金やチャット機能などは利用できません（詳細は「利用制限」セクションを参照）。



\## 1. 初期化と認証フロー



Web版APIを利用するには、まず `WebPayPay` クラスをインスタンス化し、OTPを含む2段階のログインフローを完了させる必要があります。



\### インスタンス化



```python

from oppaypay import WebPayPay



\# 電話番号とパスワードで初期化

pp = WebPayPay(

&#x20;   username="08012345678",

&#x20;   password="your\_password",

&#x20;   # 任意: 既存のトークンがある場合は指定可能

&#x20;   # access\_token="existing\_token",

&#x20;   # proxy="http://proxy.example.com:8080"

)

```



\### ログインフロー



ログインは `login()` と `login\_otp()` の2ステップで構成されます。



```python

\# 1. ログイン開始 (OTPがSMS/メールに送信される)

login\_result = pp.login()



if login\_result.get("otp\_required"):

&#x20;   # 2. ユーザーからOTPを入力してもらい、検証する

&#x20;   otp\_code = input("届いた4\~6桁のOTPコードを入力: ")

&#x20;   access\_token = pp.login\_otp(otp\_code)

&#x20;   print(f"ログイン成功! Token: {access\_token\[:20]}...")

else:

&#x20;   # OTP不要でログイン完了したケース（稀）

&#x20;   print("OTP不要でログイン完了")

```



\*\*OTP再送\*\*

OTPが届かなかった場合、`resend\_otp()` を呼び出すことで再送信を要求できます。

```python

pp.resend\_otp()

```



\---



\## 2. 利用可能な API メソッド



認証完了後、以下のメソッドを使用してPayPayアカウントの操作を行います。



\### アカウント情報



\#### `get\_profile()`

ユーザーのプロフィール情報を取得します。

\- \*\*戻り値\*\*: `Profile` (名前、PayPay ID、アバターURLなどを含む辞書ラッパー)



\#### `get\_balance()`

現在の残高（PayPayマネー、マネーライト、ポイントなど）を取得します。

\- \*\*戻り値\*\*: `Balance` (残高情報を含む辞書ラッパー)

\- \*\*例\*\*: `pp.get\_balance().all\_balance`



\#### `get\_history(size: Optional\[int] = None)`

直近の取引履歴を取得します。

\- \*\*引数\*\*:

&#x20; - `size` (`int`, 任意): 取得する件数（例: 10）

\- \*\*戻り値\*\*: `AttrDict` (履歴データ)



\---



\### 送金リンク (P2P) 操作



Web版APIで最も主要な機能の一つです。受け取った送金リンクを処理します。



\#### `link\_check(link\_or\_code: str)`

送金リンクの有効性と詳細情報を確認します。

\- \*\*引数\*\*:

&#x20; - `link\_or\_code` (`str`): `https://pay.paypay.ne.jp/xxxxxx` またはコード部分 `xxxxxx`

\- \*\*戻り値\*\*: `LinkInfo` (送信者、金額、パスワード要否などの情報)



\#### `link\_receive(link\_or\_code: str, password: Optional\[str] = None, \*, link\_info: Optional\[LinkInfo] = None)`

送金リンクを受け取り、残高に加算します。

\- \*\*引数\*\*:

&#x20; - `link\_or\_code` (`str`): 受け取るリンクまたはコード

&#x20; - `password` (`str`, 任意): リンクにパスワードが設定されている場合に必要

&#x20; - `link\_info` (`LinkInfo`, 任意): 事前に `link\_check` で取得した情報。指定するとAPI呼び出しを省略できます。

\- \*\*戻り値\*\*: `AttrDict` (受け取り成功時のレスポンス)

\- \*\*例外\*\*: 

&#x20; - `LinkAlreadyClaimed`: 既に受け取り済みまたはキャンセル済みの場合

&#x20; - `LinkPasscodeRequired`: パスワードが必要なのに指定されなかった場合



\#### `link\_reject(link\_or\_code: str, \*, link\_info: Optional\[LinkInfo] = None)`

送金リンクを辞退（キャンセル）します。

\- \*\*引数\*\*: `link\_or\_code`, `link\_info` (上記と同じ)

\- \*\*戻り値\*\*: `AttrDict` (辞退成功時のレスポンス)



\---



\### コード生成



\#### `create\_p2pcode()`

自分宛ての入金用QRコード（P2Pコード）を生成します。

\- \*\*注意\*\*: Web版APIでは金額を指定したP2Pコードの生成はサポートされていません。

\- \*\*戻り値\*\*: `P2PCode` (生成されたQRコード情報)



\#### `create\_paymentcode(method: str = "WALLET", method\_id: str = "106177237")`

店舗での支払いに使用するワンタイムコード（バーコード）を生成します。

\- \*\*引数\*\*:

&#x20; - `method` (`str`): 支払い方法タイプ（デフォルト: `"WALLET"`）

&#x20; - `method\_id` (`str`): 支払い方法ID（デフォルト: `"106177237"`）

\- \*\*戻り値\*\*: `AttrDict` (ワンタイムコード情報)



\---



\### 決済・出金



\#### `get\_barcode\_info(url\_or\_code: str)`

店舗のQRコードまたはバーコードの情報を読み取ります。

\- \*\*引数\*\*:

&#x20; - `url\_or\_code` (`str`): `https://qr.paypay.ne.jp/...` またはコード文字列

\- \*\*戻り値\*\*: `BarcodeInfo` (加盟店名、金額、orderIdなど)



\#### `pay\_qr\_code(url\_or\_code: str, \*, amount: Optional\[int] = None)`

QRコード/バーコードを読み取った後、決済を実行します。

\- \*\*引数\*\*:

&#x20; - `url\_or\_code` (`str`): 決済対象のQR/バーコード

&#x20; - `amount` (`int`, 任意): 支払い金額（コードに金額が含まれていない場合に指定）

\- \*\*戻り値\*\*: `AttrDict` (決済結果)



\#### `get\_payout\_info()`

登録されている出金先（銀行口座など）の一覧を取得します。

\- \*\*戻り値\*\*: `AttrDict` (出金先リスト)



\#### `cashout\_to\_paypaybank(amount: int, \*, payout\_method\_id: Optional\[str] = None)`

PayPay残高をPayPay銀行に出金します。

\- \*\*引数\*\*:

&#x20; - `amount` (`int`): 出金金額

&#x20; - `payout\_method\_id` (`str`, 任意): 出金先ID。指定しない場合、自動的に「PayPay銀行」またはデフォルトの口座が選択されます。

\- \*\*戻り値\*\*: `AttrDict` (出金申請結果)



\---



\### その他



\#### `get\_payment\_methods()`

アカウントに登録されている支払い方法（残高、クレジットカード、銀行口座など）の一覧を取得します。

\- \*\*戻り値\*\*: `AttrDict` (支払い方法リスト)



\---



\## 3. 利用制限と非対応機能



Web版API (`www.paypay.ne.jp/app`) は、モバイルアプリ版とバックエンドを共有していますが、プロキシレベルで以下の機能が\*\*意図的にブロック (C0000, 403, 404)\*\* されています。これらの操作を試みると `APIError` が発生します。



| 機能 | エラー理由 |

| :--- | :--- |

| \*\*直接送金\*\* (`send\_money`) | Web版APIにエンドポイントが存在しない (404) |

| \*\*送金リンクの発行\*\* (`create\_link`) | ネイティブアプリ専用の署名ヘッダーが必要 (C0000) |

| \*\*送金リンクの取消\*\* (`link\_cancel`) | ネイティブアプリ専用の署名ヘッダーが必要 (C0000) |

| \*\*チャット送信\*\* (`send\_message`) | Web版APIにエンドポイントが存在しない (404) |

| \*\*ユーザー検索\*\* (`search\_p2puser`) | Web版APIにエンドポイントが存在しない (404) |

| \*\*P2Pホーム表示\*\* (`get\_p2p\_home`) | Web版APIにエンドポイントが存在しない (404) |

| \*\*チャンネル/フィード操作\*\* | アクセス権限により拒否される (403) |



> \*\*代替案\*\*: 直接送金やリンク発行など、上記の機能を使用する必要がある場合は、モバイルアプリ版のエミュレーションまたは別の認証フローを使用する `oppaypay-desktop` の別モジュールを利用してください。



\---



\## 4. エラーハンドリング



ライブラリは、PayPay APIからのエラーレスポンスを解析し、以下のカスタム例外を送出します。`try...except` ブロックで適切に捕捉してください。



```python

from oppaypay.exceptions import (

&#x20;   AuthError, APIError, RateLimitedError, 

&#x20;   LinkAlreadyClaimed, LinkPasscodeRequired

)



try:

&#x20;   pp.link\_receive("https://pay.paypay.ne.jp/abc123")

except LinkAlreadyClaimed as e:

&#x20;   print(f"このリンクは既に処理されています: {e}")

except LinkPasscodeRequired as e:

&#x20;   print("パスワードの入力が必要です")

except RateLimitedError as e:

&#x20;   print("APIの利用制限に達しました。しばらく待機してください")

except AuthError as e:

&#x20;   print(f"認証エラー: トークンが無効または期限切れです ({e})")

except APIError as e:

&#x20;   print(f"APIエラー: {e.code} - {e}")

```



\### 主な例外クラス

\- `AuthError`: ログイン失敗、OTP検証失敗、トークンの無効化。

\- `APIError`: 汎用的なAPIエラー。`e.code` にPayPay固有のエラーコード（例: `E\_WEB\_UNAVAILABLE`, `E\_NO\_ORDER\_ID`）が含まれます。

\- `RateLimitedError`: HTTP 429 Too Many Requests。

\- `LinkAlreadyClaimed`: 送金リンクが既に受け取り済み、辞退済み、またはキャンセル済みの場合。

\- `LinkPasscodeRequired`: パスワード付きリンクに対して `password` 引数が渡されなかった場合。



\---



\## 5. 内部実装の補足 (Raw API)



`WebPayPay` クラスは、発見されたBFFエンドポイントを直接叩くための低レベルラッパー `pp.raw` を内部に保持しています。

```python

\# 例: ドキュメント化されていないエンドポイントを直接叩く（自己責任）

response = pp.raw.get\_balance\_info()

```

ただし、前述の「利用制限」に該当するパスを `pp.raw` 経由で呼び出しても、プロキシレベルでブロックされるため注意が必要です。

