<img width="91" height="89" alt="logo" src="https://github.com/user-attachments/assets/cfafe8d9-4e3d-4975-b39c-ecb920d6e9ec" /> 
---

# oppaypay

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-0.4.1-green)](https://github.com/xpof/oppaypay)
[![License](https://img.shields.io/badge/license-MIT-gray)](LICENSE)

非公式 PayPay API クライアントライブラリ。高度なボット検知回避機構と、人間らしい動作シミュレーションを備えた実戦向け (Production-ready) 実装です。

## 🚀 主な特徴 (Features)

- **🧠 エントロピーベースの人間化ディレイ**: `time.sleep(固定値)` のようなマジックナンバーを完全排除。OS レベルの乱数と URL ハッシュに基づいて、毎回予測不可能で自然な待機時間を自動生成します。
- **🌐 堅牢な AWS WAF チャレンジ処理**: ログインフロー中に発生する WAF の JS チャレンジ（202レスポンス）を安全に検出・解決。HTML レスポンスに対して `response.json()` を呼び出してクラッシュする致命的なバグを解消しました。
- **🔄 スマートリトライ機構**: 429 (Rate Limit) や 5xx サーバーエラーに対して、ランダムな待機時間を挟むインテリジェントなリトライを実装。
- **🔗 安全な URL パーシング**: QR コード URL の処理において、単純な `replace` による予期せぬ文字列破壊バグを修正。
- **🛡️ 高度なボット検知回避**: `curl_cffi` による TLS フィンガープリントの偽装と、デバイスセンサー情報の動的生成。
- **📱 フル機能サポート**: ログイン (PKCE / OTL 対応)、残高照会、QR コード決済、P2P 送金コード作成、セッションリフレッシュ。

## 📦 インストール

```bash
pip install oppaypay
```

**主な依存関係:**
- `curl_cffi` (TLS フィンガープリント偽装用)
- `pkce` (PKCE フロー用)

## ⚡ クイックスタート

### 1. 基本的なログインと残高照会

```python
from oppaypay import PayPayCore

# 初期化 (humanize=True で人間らしい動作をシミュレート。デフォルトで True)
core = PayPayCore(
    phone="09012345678",
    password="your_password",
    humanize=True  
)

# ログイン開始 (未登録デバイスの場合は OTL (ワンタイムリンク) フローへ移行)
core.login_start()

# ※ 未登録デバイスの場合、スマホに届いた OTL の URL を渡して認証を完了させます
# core.login_confirm("https://www.paypay.ne.jp/portal/oauth2/l?id=xxxxx")

# 残高照会
balance = core.get_balance()
print(f"総残高: {balance.all_balance} 円")
print(f"PayPayマネー: {balance.money} 円")
```

### 2. QR コード決済

```python
# QR コードの URL またはコード文字列を渡す
qr_url = "https://qr.paypay.ne.jp/xxxxxxxxxxxx"
result = core.pay_qr_code(qr_url)
print("決済結果:", result["header"]["resultCode"])
```

## ⚙️ 高度な設定

### プロキシの使用
```python
core = PayPayCore(
    phone="09012345678",
    password="your_password",
    proxy="http://user:pass@proxy.example.com:8080",
    humanize=True
)
```

### セッションの維持 (Device UUID の固定)
アカウント凍結リスクを最小化するため、成功したログイン後は `device_uuid`、`client_uuid`、`refresh_token` を安全な場所に保存し、次回以降はそれらを使用して初期化することを**強く推奨**します。

```python
# 初回ログイン成功後に保存すべき情報
print("Device UUID:", core.device_uuid)
print("Client UUID:", core.client_uuid)
print("Refresh Token:", core.refresh_token)

# 次回以降の初期化 (電話番号/パスワード不要)
core = PayPayCore(
    access_token="saved_access_token",
    refresh_token="saved_refresh_token",
    device_uuid="saved_device_uuid",
    client_uuid="saved_client_uuid",
    humanize=True
)

# トークンが切れている場合は自動更新
if not core.access_token:
    core.refresh_session()
```

---

## 📝 v0.4.1 変更点・リリースノート (Changelog)

v0.4.1 では、旧バージョン（v0.4.0以前）のコードに存在した**構造的な矛盾とクラッシュリスク**をすべて解消し、実運用に耐えうる堅牢性を備えました。

### 🛠️ 致命的なバグ修正 (Critical Fixes)
- **[FIX] WAF チャレンジ時のクラッシュ解消**: 
  旧バージョンでは、AWS WAF によって `202 Accepted` (HTML) が返された際に `response.json()` を実行し `JSONDecodeError` でクラッシュしていました。v0.4.1 では `_web_request` ヘルパーを導入し、WAF チャレンジの自動解決と安全な再リクエストをカプセル化しました。
- **[FIX] 状態管理の不備 (`AttributeError`) 解消**: 
  `login_start` が失敗した際に `self._login_headers` が未定義となり、後続の `login_confirm` で `AttributeError` が発生する問題を修正。`__init__` 内で安全に初期化するよう変更しました。
- **[FIX] URL パーシングの堅牢化**: 
  `get_barcode_info` や `pay_qr_code` における URL 処理で、単純な `str.replace()` を使用していたため、予期せぬ箇所が置換されるバグがありました。`startswith` と `rstrip("/")` を用いた安全な抽出ロジックへ修正しました。

### 🚀 新機能・改善 (Features & Improvements)
- **[FEAT] エントロピーベースの人間化ディレイ (`_human_delay`)**: 
  旧バージョンにはリクエスト間の待機処理（`time.sleep`）が一切なく、ミリ秒単位で連続リクエストを行うためボット検知の格好の的でした。v0.4.1 では、OS の乱数（`secrets`）と URL のハッシュ値を用いた「ランダムウォーク（酔歩）モデル」を採用。開発者がチューニングするマジックナンバーを完全排除し、毎回予測不可能な自然な待機時間を生成します。
- **[FEAT] スマートリトライ機構**: 
  `request` メソッドにリトライロジックを追加。429 (Rate Limit) や 5xx サーバーエラー発生時に、即座に失敗するのではなく、ランダムな待機時間を挟んでから再試行するようになりました。
- **[REFACTOR] リクエストエンジンの責務分離**: 
  JSON を扱う API 用 (`request`) と、HTML/WAF を扱う Web ポータル用 (`_web_request`) でメソッドを明確に分離。コードの可読性と保守性が飛躍的に向上しました。

---

## ⚠️ 注意事項・免責事項 (Disclaimer)

- **非公式ライブラリ**: このライブラリは PayPay 株式会社とは一切関係がなく、公式にサポートされているものではありません。
- **利用規約**: 自動化スクリプトの使用は PayPay の利用規約に違反する可能性があります。
- **アカウント凍結のリスク**: 本ライブラリは v0.4.1 で高度な回避機構を備えましたが、100% 検知を回避できることを保証するものではありません。過度な連打や不自然な利用はアカウント凍結の原因となります。**自己責任**でご利用ください。
- **本番環境での利用**: 実際の資金を扱うため、まずは少額での動作確認を強く推奨します。

## 🤝 Contributing

プルリクエストや Issue 報告を歓迎します。ただし、セキュリティやボット検知回避に関わる変更は、その合理性と検知回避への寄与を明確に説明してください。

## 📜 License

MIT License
