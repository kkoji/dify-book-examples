# 検証記録: observability 章

- 日付: 2026-10-05(初回検証は 2026-10-03、前任エージェントが中断したため本日再実行)
- 環境: Dify 1.17.1(セルフホスト、Docker Compose)、Ollama `qwen2.5:7b`(プラグイン `langgenius/ollama` 1.0.2)、Python 3.10.16 / httpx 0.28.1 / PyYAML 6.0.2 / python-dotenv 1.1.1(`python/.venv`)
- 外部コンポーネント: Langfuse `docker.langfuse.com/langfuse/langfuse:4.50.0` + `langfuse-worker:4.50.0`(ClickHouse 25.12、PostgreSQL 17.6、Redis 7.4、MinIO)、OTel Collector `otel/opentelemetry-collector-contrib:0.161.0`
- Console API のログインは 2026-10-03 のセッションがそのまま有効だった。Service API キーは scratchpad の `wf_apikey.json`(support-triage)と `smoke_app_key`(smoke: chatbot)を再利用
- 評価対象: workflow 章の `workflow: support-triage`(app_id `b8892499-4bc5-4ce1-9f0e-9d59f96f2e88`)。公開済みバージョンは v1 のみ(`workflow_id` `a5fea09c-ea48-4f17-ad50-79fd6fc05b5a`、version 文字列 `2026-10-02 19:36:23.821225`)

## サンプル 1: python/eval/(run_eval.py、judge.py、testcases.yaml)

- コマンド: `cd python && DIFY_APP_API_KEY=<support-triage のキー> .venv/bin/python eval/run_eval.py --workflow-id a5fea09c-ea48-4f17-ad50-79fd6fc05b5a --judge --out <scratchpad>/eval_result_v1_20261005.json`
- 結果(2026-10-05): 8 ケース中 8 件 PASS(`category` 一致率 1.0、`needs_human` を書いた 3 ケースも一致)、`judge_avg` 3.0。全実行 `succeeded`、6 ステップ、11.7〜58.8 秒(Langfuse 送信とチャットボット検証を並行したため後半が遅い)
- 過去の実行: 2026-10-03 に `--workflow-id` 指定で 8/8(judge_avg 3.0)、同日 `POST /workflows/run`(現在の公開版 = v1)で 8/8(judge_avg 2.75)。計 3 回とも `category` は全件一致
- 揺れの記録: `expense-per-diem`(出張の日当)の `answer` は 3 回中 2 回で「是 ragazzo …」のように中国語などが混じった(workflow 章の検証と同じ現象)。この回答に対する judge の採点は 2026-10-03 が 2 点、2026-10-05 が 3 点で、同じ qwen2.5:7b を採点に使うと採点側も揺れる。本文はこの事実をそのまま書いた
- 結果: 成功

## サンプル 2: python/export_feedback.py

- フィードバック送信: `smoke: chatbot`(app_id `c57da944-40ea-438f-a567-3d79689d276b`、mode `chat`)に `POST /v1/chat-messages`(blocking、user `obs-check-1005`)→ message_id `d4242e0a-db9c-4145-83d0-669a79a6c7d4`、`POST /v1/messages/<id>/feedbacks`(`rating: dislike`、`content` 付き)→ `{"result":"success"}`
- `export_feedback.py feedbacks`(chatbot のキー)→ 2 行(本日分と 2026-10-03 分)。各行に `conversation_id` / `message_id` / `rating` / `content` / `from_end_user_id` が入る。応答に `has_more` が無いことを前提にした空ページ停止で正常終了
- `export_feedback.py messages --user obs-check-1005` → 1 行(会話 + メッセージ、`feedback.rating: dislike`)
- `export_feedback.py workflow-logs`(support-triage のキー)→ 36 行。各行の `workflow_run.version` に公開時のバージョン文字列、`created_by_end_user.session_id` に Service API の `user`(例 `eval-runner`、`langfuse-check-1005`)が入る。`--status failed` → 0 行(失敗実行が無いため。フィルタ自体は 200 で返る)
- chatbot のキーで `GET /v1/workflows/logs` → 200、`total: 0`(本文の「Chatflow / Chatbot には効かない」の根拠)
- 結果: 成功

## サンプル 3: ops/langfuse/

- 起動: `cd ops/langfuse && docker compose up -d`(`.env` は 2026-10-03 に作成済み、gitignore 対象)。約 60 秒で `curl http://localhost:3000/api/public/health` → `{"status":"OK","version":"4.50.0"}`
- Dify 側設定(Console API): `POST /console/api/apps/<id>/trace-config` は 2026-10-03 の設定が残っているため 409 `trace_config_already_exists`。`PATCH` 同パスに同じ body(`public_key` / `secret_key` / `host: http://host.docker.internal:3000`)→ `{"result":"success"}`(到達確認を通過)。`POST /console/api/apps/<id>/trace` `{"enabled":true,"tracing_provider":"langfuse"}` → success、`GET /apps/<id>/trace` → `{"enabled":true,"tracing_provider":"langfuse"}`
- 実行: `POST /v1/workflows/run`(user `langfuse-check-1005`、質問「プリンタに接続できません。…」)→ `succeeded`、run_id `fd8fb211-d755-4c1f-9650-66fa9617fb63`
- 確認: `GET http://localhost:3000/api/public/traces/<run_id>`(Basic 認証 pk:sk)で約 20 秒後に取得。`name: workflow`、`userId: langfuse-check-1005`、`tags: ["workflow"]`、`version` に公開時バージョン文字列、`input` に `question` と `sys.*`、`output` に `{category, answer, needs_human}`、`metadata` に `workflow_id` / `workflow_run_id` / `total_tokens` / `elapsed_time` / `triggered_from` など。observation は 6 件で全件 `parentObservationId: null`(平ら): GENERATION 2 件(Question Classifier、LLM: IT、いずれも `model: qwen2.5:7b` と usage 付き)、SPAN 4 件(User Input、Code: normalize、Variable Aggregator、Output)。本文の表と段落はこの結果に一致
- `LANGFUSE_MIGRATION_V4_WRITE_MODE=dual` を入れた Compose で受け付けられることを再確認(2026-10-03 の `events_only` 拒否は research メモ追記のとおり)
- 後始末: `POST /apps/<id>/trace` `{"enabled":false}` で無効化(Langfuse を落とすため。trace-config 自体は残してあるので、著者が Langfuse を再起動して有効化すれば GUI で「In use」を確認できる)、`docker compose down`(ボリュームは残した)
- 結果: 成功。GUI の「Tracing app performance」パネルの表示とスクリーンショットは著者確認待ち

## サンプル 4: ops/otel/

- 起動: `cd ops/otel && docker compose up -d` → `curl http://localhost:13133` → `{"status":"Server available",...}`
- パイプライン確認: 手元から `POST http://localhost:4318/v1/traces`(OTLP/JSON、service.name `obs-check` のスパン 1 件)→ 200。`docker compose logs otel-collector` に `Traces ... "spans": 1` と `ResourceTraces #0 service.name=obs-check` が出た
- Dify 側の `ENABLE_OTEL=true` は未実施(`vendor/dify/docker/.env` を他章と共有しており変更しない方針)。本文に VERIFY を残した。`dify-otel.env.example` の「`.env` の値が優先」は `docker/README.md` の記述に基づく(api / worker の `environment:` ブロックに OTel 系の行が無いため、実際に `.env` 追記だけで渡るかは要実機確認。research メモに追記)
- 後始末: `docker compose down`
- 結果: Collector の起動と受信は成功、Dify からの送信は著者確認待ち

## 本文に残した目印(`books/dify-for-code-first-engineers/observability.md`)

| 行 | 種別 | 内容 |
| --- | --- | --- |
| 11 | SCREENSHOT | Monitoring 画面の 4 指標 |
| 15 | VERIFY | Logs 一覧の列名と会話詳細の項目名 |
| 16 | SCREENSHOT | Logs の会話詳細(ノード別トレース) |
| 24 | VERIFY | Add Features の Annotation Reply 項目名と Similarity Threshold 既定値 |
| 32 | VERIFY | Tracing app performance に 10 プロバイダが並ぶか |
| 33 | SCREENSHOT | Tracing app performance(Langfuse が In use) |
| 59 | SCREENSHOT | Langfuse の trace 詳細(observation 6 件) |
| 63 | VERIFY | OPS_TRACE_UNIFIED_ENABLED=true 時の Phoenix / LangSmith の見え方 |
| 64 | TODO(要確認) | PR #39339 の GenAI スパンが他プロバイダで見えるか |
| 70 | TODO(要確認) | OTel のメトリクス種類、ワークフロー実行が OTel スパンになるか |
| 83 | VERIFY | ENABLE_OTEL=true で Collector にスパンが届くか |
| 140 | AUTHOR | 実運用での所感 |

(行番号は 2026-10-05 時点)

## 分量

- 本文文字数: 5999 字(コードブロック・コメント・空白を除く。前任の下書き 6,171 字から節構成を変えずに削った)

## 申し送り

- `python/requirements.txt` の `mcp==1.30.0` と `python/.env.example` の `DIFY_DATASET_ID` は本章のものではない(それぞれ tools-mcp 章の `mcp_call_dify.py`、knowledge 章の `knowledge_retrieve.py` 用)。本章の追加依存は無い
- `ops/langfuse/.env` は gitignore 対象で、`.env.example` のみコミットする
- 本文末尾の「次の章では公開版を DSL としてどう管理するか」は dsl-versioning 章を指す。config.yaml の章順で本章の後ろに dsl-versioning が来ない場合は、この 1 文を直す
