# 検証記録: production-config

- 日付: 2026-10-03
- Dify: 1.17.1(セルフホスト、Docker Compose。`vendor/dify` はタグ 1.17.1、commit 8387590)
- Docker 29.8.1 / Docker Compose v5.5.1(macOS)
- LLM: この章のサンプルはモデルを使わない(Ollama 不要)
- 本文の文字数: 5,987(`count_chars.py`、コードブロック・コメント・空白を除く)

## 環境変数の実物確認

本文に書いた変数名・既定値・置き場所は、稼働中の `vendor/dify/docker/.env.example`、`envs/*/*.env.example`、`docker-compose.yaml`(タグ 1.17.1)を grep して確認した。調査メモとの食い違いと新たに分かったことは `research/dify-for-code-first-engineers/deployment.md` と `limits-migration.md` に追記した。

| 確認した事柄 | 方法 | 結果 |
| --- | --- | --- |
| 開発用シークレット 9 種が `.env.example` にあること | grep | `SECRET_KEY=`(空)、`DB_PASSWORD` / `REDIS_PASSWORD` = `difyai123456`、`WEAVIATE_API_KEY`、`SANDBOX_API_KEY` / `CODE_EXECUTION_API_KEY` = `dify-sandbox`、`PLUGIN_DAEMON_KEY`、`PLUGIN_DIFY_INNER_API_KEY`、`DIFY_AGENT_API_TOKEN`、`DIFY_AGENT_SERVER_SECRET_KEY` を確認。メモと一致 |
| `S3_*`、`MAIL_TYPE` / `SMTP_*`、`ALLOW_REGISTER`、`WORKFLOW_LOG_CLEANUP_ENABLED`、`ENABLE_CLEAN_MESSAGES`、`ENABLE_OTEL`、`OPS_TRACE_UNIFIED_ENABLED`、`APP_MAX_ACTIVE_REQUESTS` の置き場所 | grep | すべて `.env.example` に無く `envs/core-services/shared.env.example` にある。`SANDBOX_EXPIRED_RECORDS_RETENTION_DAYS` は `envs/core-services/sandbox.env.example` のみ(api / worker の env_file には含まれない) |
| `CERTBOT_*` の置き場所 | grep | `envs/infrastructure/certbot.env.example` のみ。nginx サービスは `${CERTBOT_DOMAIN:-}` の補間で読む |
| Compose 補間は `.env` からしか読まないこと | scratchpad に `docker/` をコピー(volumes と .env を除く)し、`.env.example` から `NGINX_HTTPS_ENABLED` を除いた `.env` を作成。`envs/infrastructure/nginx.env` に `NGINX_HTTPS_ENABLED=true` を置いて `docker compose config` | nginx の `NGINX_HTTPS_ENABLED` は `"false"` のまま。同じ値を `.env` に書くと `"true"` になった |
| `.env` が `envs/*.env` より優先されること | 同上。`envs/core-services/shared.env` に `ALLOW_REGISTER=true` と `STORAGE_TYPE=s3` を置き `docker compose config` | api の `ALLOW_REGISTER` は `"true"`(`.env.example` に無い変数)、`STORAGE_TYPE` は `opendal` のまま(`.env` にある変数は `.env` が勝つ) |
| `SECRET_KEY` 自動生成の保存先 | `api/configs/secret_key.py` を読む、`ls -la vendor/dify/docker/volumes/app/storage/` | `.dify_secret_key` をストレージ経由で保存。稼働環境に `volumes/app/storage/.dify_secret_key`(65 バイト)が存在 |
| ストレージ移行コマンド | `api/commands/storage.py` を grep | 1.17.1 にあるのは `flask migrate-oss`。公式ドキュメントの `upload-local-files-to-cloud-storage` 等は存在しない(メモに追記) |
| `agent_backend` 系を止められるか | `docker-compose.yaml` を読む | 3 サービスは profile なし。`api` の `depends_on` に `agent_backend: condition: service_started`(`required: false` なし)。停止後の挙動は未検証(本文に TODO) |
| ホストに公開されるポート | `docker-compose.yaml` の `ports:` を grep | 既定 profile では nginx(80 / 443)と plugin_daemon(5003)のみ |
| ログ削除タスクの対象 | `api/extensions/ext_celery.py`、`api/schedule/clean_workflow_runlogs_precise.py`、`api/schedule/clean_messages.py` を読む | 2:00 の `clean_workflow_runlogs_precise` は workflow_runs、node executions、紐づく messages 系、conversations、トリガーログを削除。4:00 の `clean_messages` はセルフホストでは全テナントが対象。`ENABLE_CONVERSATION_CLEANUP_TASK` は保持期間削除ではなく削除ジョブの再キュー(limits-migration.md のメモを訂正) |

## サンプルの検証

### `ops/env.production.example`

- 作成のみ。値はダミーで、各行に置き場所ラベル(`[.env]` / `[shared.env]` / `[certbot.env]` / `[両方]`)を付けた
- 変数名はすべて上記 grep で実物に存在することを確認した

### `ops/docker-compose.override.example.yaml`(MinIO、`STORAGE_TYPE=s3`)

- 稼働中の Dify を壊さないため、**起動はしていない**。構文確認のみ
- 手順: scratchpad の `dify-docker-copy/`(`vendor/dify/docker` のコピー、`.env` は `.env.example` のコピー)に override を置き、`docker compose -f docker-compose.yaml -f docker-compose.override.example.yaml config` を実行
- 結果: 成功(exit 0、警告なし)。サービス一覧に `dify_minio` が追加され、`api` / `worker` / `worker_beat` / `api_websocket` の環境に `STORAGE_TYPE: s3`、`S3_ENDPOINT: http://dify_minio:9000`、`S3_ADDRESS_STYLE: path`、`S3_ACCESS_KEY: minioadmin` が入ることを確認
- 実際に MinIO で起動して `flask migrate-oss` まで通す検証は著者確認待ち(ローカルの Dify を一度止める必要があるため)

### `ops/backup.sh`

- 実行コマンド: `DIFY_DOCKER_DIR=/Users/kojimakazuya/Projects/zenn-content/vendor/dify/docker BACKUP_DIR=<scratchpad>/backups ./backup.sh`(`STOP_CONTAINERS` なし、稼働したまま)
- 結果: 成功(exit 0)。`<scratchpad>/backups/dify-backup-20261003-043506/` に `postgres.sql.gz`(47 KB、`CREATE TABLE` 144 件)、`volumes.tar.gz`(65 MB、`volumes/app` `certbot` `db` `plugin_daemon` `redis` `sandbox` `weaviate` ほかを含む)、`manifest.txt` が生成された
- `pg_dump` はコンテナ内の `POSTGRES_USER` / `POSTGRES_DB` を使うため、スクリプトは `.env` を読まない
- `STOP_CONTAINERS=1` の経路(stop → tar → start)は稼働中の環境を止めるため未実行。著者確認待ち
- 復元手順(tar 展開 → `psql` で流し込み)は本文の範囲外とし、未検証

## 本文に残した目印

| 行 | 種別 | 内容 |
| --- | --- | --- |
| 63 | VERIFY | メール未設定時にメンバー招待画面へ共有リンクが表示されること(著者が実機で確認) |
| 75 | TODO(要確認) | agent_backend / local_sandbox / agent_ssrf_proxy を stop しても api が動くか、docker-compose.yaml を編集せずに外す方法 |
| 81 | TODO(要確認) | Compose で api / worker を複数レプリカにしたときのローカルストレージの扱い |

SCREENSHOT: なし。章仕様にあった `SECRET_KEY` 自動生成の保存先の TODO は、コードと実機で `.dify_secret_key` を確認したので本文に書き、TODO を外した。

## 他章への申し送り

- setup 章: `.env.example` を丸ごと `.env` にコピーする手順を書くと、`envs/*.env` の同名変数が無視される。`.env` 側を書き換えるよう一言入れるとよい
- observability 章: `ENABLE_OTEL` / `OTLP_BASE_ENDPOINT` / `OPS_TRACE_UNIFIED_ENABLED` は `shared.env.example` にあり `.env.example` には無い。`API_SENTRY_DSN` / `WEB_SENTRY_DSN` は `.env.example` にある
- knowledge 章: 公式ドキュメントのストレージ移行コマンド名と 1.17.1 の `flask migrate-oss` が食い違う。ナレッジのファイル移行に触れるならこちらを使う
- new-agent 章: サンドボックス分離の公式注意は本章に置いた。new-agent 章からは「production-config 章を参照」で足りる
