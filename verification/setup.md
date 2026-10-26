# 検証記録: setup

- 日付: 2026-10-03
- Dify: 1.17.1(セルフホスト、Docker Compose、`docker/.env.example` を無変更で `.env` にした構成)
- Docker 29.8.1 / Docker Compose v5.5.1(macOS、Docker Desktop)
- Ollama: `qwen2.5:7b`(LLM)、`nomic-embed-text`(埋め込み)。Dify 側プラグイン `langgenius/ollama` 1.0.2、Base URL `http://host.docker.internal:11434`

## サンプル

### `ops/env.local.example`

- 内容: setup 章時点で `docker/.env` に加えた変更の記録。`diff <(sort .env.example) <(sort .env)` が空だったため「変更なし」と明記し、以降の章で追記しそうな候補をコメントで列挙した
- 結果: 成功(記録のみ。実行するものではない)

### `python/smoke_test.py`

- 対象アプリ: `smoke: chatbot`(app_id `c57da944-40ea-438f-a567-3d79689d276b`、mode `chat`、モデル `qwen2.5:7b`)。統括側が作成済みのものを使用
- API キー: scratchpad の `smoke_app_key`(リポジトリには置かない)
- 実行コマンド(`python/.env` に `DIFY_API_BASE=http://localhost/v1` と `DIFY_APP_API_KEY` を一時的に書いて実行し、実行後に削除):

```bash
examples/dify-for-code-first-engineers/python/.venv/bin/python \
  examples/dify-for-code-first-engineers/python/smoke_test.py "Dify のセットアップ確認です。1 文で挨拶してください"
```

- 結果: 成功(HTTP 200、所要 1.2 秒)

```text
answer: Difyのセットアップ確認 helful なサポートを提供しますよ。
conversation_id: a93d4ac9-38a3-4f15-beba-68c9718c1509
usage: prompt_tokens 44 / completion_tokens 17 / total_tokens 61 / total_price "0" / currency USD / latency 0.8787617089983542
```

- 補足: 初版は `load_dotenv()` 引数なしだったが、python-dotenv はスクリプトのディレクトリから `.env` を探すため、cwd に置いた `.env` が読まれなかった。`load_dotenv(Path(__file__).with_name(".env"))` に変更し、`python/.env.example` と同じ場所の `.env` を読む仕様にした

### 本文に載せた `curl`

- `POST http://localhost/v1/chat-messages`(blocking)。smoke_test.py と同じリクエスト本文なので個別には実行していない。応答フィールドは research/service-api.md の `ChatCompletionResponse` と実行結果で一致を確認

## 根拠の突き合わせ

- `vendor/dify/docker/docker-compose.yaml` のサービス一覧(api, api_websocket, worker, worker_beat, web, plugin_daemon, agent_backend, db_postgres, redis, weaviate, nginx, ssrf_proxy, agent_ssrf_proxy, sandbox, local_sandbox, init_permissions)と各イメージは research/deployment.md の記述と一致。`docker compose ps` では 15 コンテナが Up(init_permissions は一回限りで終了済み、db_mysql / certbot は profile で除外)
- `vendor/dify/docker/.env.example` の既定値(`SECRET_KEY=` 空、`SSRF_PROXY_HTTP_URL`、`CODE_EXECUTION_ENDPOINT`、`MARKETPLACE_ENABLED=true`、`FORCE_VERIFYING_SIGNATURE=true`、`MIGRATION_ENABLED=true`)は deployment.md / tools-mcp.md と一致。食い違いなし
- nginx の `default.conf.template` に `location /console/api`、`/v1`、`/` があることを確認(本文の表の nginx 行)
- Ollama の Add Model 項目名は、稼働中の Dify の `GET /console/api/workspaces/current/model-providers` が返す資格情報フォーム(en_US ラベル)と公式プラグインの README で確認し、deployment.md に追記した。「Integrations > Model Provider」「Install」「Setup」「Add Model」は docs.dify.ai の Model Providers ページ(クラウド版向け)で確認し、セルフホストでの導線は VERIFY 扱い

## 本文に残した目印(books/dify-for-code-first-engineers/setup.md)

| 行 | 種別 | 内容 |
| --- | --- | --- |
| 34 | SCREENSHOT | `http://localhost/install` の管理者アカウント作成画面 |
| 84 | VERIFY | Model Provider 画面の Install ボタンの位置、Add Model の項目名、Model Type の選択肢表記 |
| 88 | TODO(要確認) | Linux の Docker で `host.docker.internal` を解決させる方法(公式の現行 Ollama ページが 404) |
| 102 | SCREENSHOT | Choose an App Type のモーダル(More basic app types を展開した状態) |
| 103 | VERIFY | Create from Blank ボタンの位置、Chatbot のモデル選択と公開(Publish)の導線 |
| 107 | SCREENSHOT | API Access 画面(Backend Service API カードと API Key のモーダル) |
| 108 | VERIFY | API Access → Backend Service API → API Key → Create new Secret key の順序 |

## 本文の文字数

- 5,231 字(コードブロック・コメント・空白を除く、count_chars.py)。章仕様の目安 3,500〜5,000 字をわずかに超えるが、CLAUDE.md の上限 6,000 字には収まる。16 コンポーネントの表(約 500 字)が主因
