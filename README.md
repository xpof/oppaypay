<img width="91" height="89" alt="logo" src="https://github.com/user-attachments/assets/cfafe8d9-4e3d-4975-b39c-ecb920d6e9ec" />  

# oppaypay v.0.4.2

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-0.4.2-green)](https://github.com/xpof/oppaypay)
[![License](https://img.shields.io/badge/license-MIT-gray)](LICENSE)

非公式 PayPay API クライアントライブラリ。**「有機的な人間行動シミュレーション」**と**「高度なAWS WAF自動解決」**を統合し、実運用での安定性と検知回避能力を飛躍的に高めた次世代実装です。

## 🚀 v0.4.2 の主な特徴

- **🧬 有機的 Human Pattern Simulator**: 固定値（マジックナンバー）を完全排除。OSエントロピー、URLハッシュ、そして内部状態（集中力・フロー）に基づき、毎回予測不可能で自然な待機時間と微細なセンサーの揺らぎを生成します。
- **📱 iOS 26.6 完全対応**: TLSフィンガープリント、User-Agent、デバイスヘッダーを環境に応じて動的に最適化。整合性の取れた偽装を行います。
- **💾 柔軟なセッション管理**: `session_id` を指定することで、アクセストークンやデバイスUUIDを自動保存・復元。2FA（OTL）をスキップした高速な再接続が可能です。
- **🔄 スマートリトライ機構**: 429 (Rate Limit) や 5xx エラーに対して、ランダムな待機時間を挟むインテリジェントな再試行ロジックを搭載。

## 📦 インストール

```bash
pip install oppaypay
```

**主な依存関係:**
- `curl_cffi` (TLS フィンガープリント偽装用)
- `pkce` (PKCE フロー用)
- `cryptography` (WAF 暗号化用)
- `pyyaml` (GPU プロファイル管理用)

## ⚡ クイックスタート

### 1. 基本的なログインと残高照会

```python
from oppaypay import PayPayCore

# セッションIDを指定すると、過去の状態が自動復元されます
core = PayPayCore(
    phone="09012345678",
    password="your_password",
    session_id="my_iphone_session", # 任意のID
    humanize=True  # 有機的な人間偽装を有効化
)

# ログイン開始（未登録デバイスの場合はOTLフローへ移行）
if not core.access_token:
    print("ログイン開始...")
    core.login_start()
    # OTL確認が必要な場合はここで実行
    # core.login_confirm("https://www.paypay.ne.jp/portal/oauth2/l?id=xxxxx")
else:
    print("保存されたセッションから復元しました。")

# 残高照会
balance = core.get_balance()
print(f"総残高: {balance.all_balance} 円")
print(f"PayPayマネー: {balance.money} 円")
```

### 2. 有機的な人間行動シミュレーション 

単なるAPI呼び出しではなく、指先の震えや集中力の揺らぎを模倣したセッションを実行できます。

```python
from oppaypay._alive import simulate_human_behavior

# 有機的なホーム画面訪問と履歴確認をシミュレート
simulate_human_behavior(core)
```

### 3. QR コード決済

```python
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

### デバイス情報の固定
アカウント凍結リスクを最小化するため、成功したログイン後は `device_uuid` や `client_uuid` を固定することを推奨します。`session_id` を使用すればこれらは自動で管理されます。

## 📝 v0.4.2 変更点・リリースノート (Changelog)

### 🛠️ 致命的なバグ修正 (Critical Fixes)
- **[FIX] WAF 202応答でのクラッシュ解消**: `_web_request` ヘルパーを導入し、AWS WAF チャレンジ（HTML）に対して `response.json()` を実行してクラッシュする問題を完全に解消。
- **[FIX] `_login_headers` の AttributeError 防止**: `__init__` で初期化を行い、未定義属性によるエラーを防止。
- **[FIX] 危険な URL 処理の修正**: `str.replace()` による予期せぬ文字列破壊を防ぐため、`startswith` とスライスを使用した堅牢な処理に変更。

### 🚀 新機能・改善 (Features & Improvements)
- **[FEAT] 有機的 Human Pattern Simulator (`_alive.py`)**: マジックナンバーを排除した `_organic_wait` と、静止時でも発生する微細なセンサーの揺らぎ `_simulate_micro_tremors` を実装。
- **[FEAT] エントロピーベースの遅延 (`_human_delay`)**: OS乱数とURLハッシュを用いた「ランダムウォーク（酔歩）モデル」により、毎回異なる統計分布を持つ自然な待機時間を生成。
- **[FEAT] 強化された WAF ソルバー (`_awswaf`)**: Scrypt, SHA256, NetworkBandwidth チャレンジを自動判別・解決する統合ソルバーを搭載。
- **[FEAT] セッション管理の柔軟性向上**: `session_id` による名前付きセッションの保存・復元機能を追加。

## ⚠️ 注意事項・免責事項 (Disclaimer)

- **非公式ライブラリ**: このライブラリは PayPay 株式会社とは一切関係がなく、公式にサポートされているものではありません。
- **利用規約**: 自動化スクリプトの使用は PayPay の利用規約に違反する可能性があります。
- **アカウント凍結のリスク**: 本ライブラリは高度な回避機構を備えていますが、100% 検知を回避できることを保証するものではありません。過度な連打や不自然な利用はアカウント凍結の原因となります。**自己責任**でご利用ください。
- **本番環境での利用**: 実際の資金を扱うため、まずは少額での動作確認を強く推奨します。

## 🤝 Contributing

プルリクエストや Issue 報告を歓迎します。特に、ボット検知回避や有機的シミュレーションに関する知見の共有は大歓迎です。

## 📜 License

MIT License
