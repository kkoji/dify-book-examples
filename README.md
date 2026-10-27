# examples: dify-for-code-first-engineers

本「LangChain / LangGraph 経験者のための Dify 実践ガイド: PoC から本番運用まで」のサンプル置き場。

## 検証環境

| 項目 | 値 | 確認日 |
| --- | --- | --- |
| Dify | 1.17.1(セルフホスト、Docker Compose、`docker/.env.example` をそのまま `.env` にした構成) | 2026-10-03 |
| Docker / Compose | 29.8.1 / v5.5.1(macOS) | 2026-10-03 |
| LLM | Ollama `qwen3:8b`(Dify プラグイン `langgenius/ollama` 1.0.2、Base URL `http://host.docker.internal:11434`) | 2026-10-03 |
| 埋め込み | Ollama `nomic-embed-text` | 2026-10-03 |
| Python(API を呼ぶスクリプト `python/`) | 3.10.16、依存は `python/requirements.txt` で固定 | 2026-10-03 |
| Python(サーバー系 `tools/*`、`python/hybrid`) | 3.12.10、依存は各ディレクトリの `requirements.txt` で固定 | 2026-10-06 |

OpenAI などのクラウドモデルに切り替える場合は、DSL をインポートした後に LLM ノード(または Chatbot のモデル設定)でモデルを選び直す。

補足: Dify から呼ばれるサーバー(`tools/*`)と `python/hybrid` は Python 3.12.10、Dify の API を呼ぶだけのスクリプト(`python/` 直下)は 3.10.16 で検証した。もう一方の版で動くかは確認していないので、再現するときはこの版に合わせる。

## ディレクトリ

- `dsl/`: 各章で作るアプリの DSL(Dify 1.17.1 でエクスポート、`version: 0.7.0`)。Studio の「Import DSL file」で取り込む
- `python/`: Service API / Knowledge API を呼ぶ Python スクリプト。章ごとの単体スクリプト(`smoke_test.py`、`run_workflow.py`、`chat_multiturn.py`、`stream_agent.py`、`stream_new_agent.py`、`knowledge_ingest.py`、`knowledge_retrieve.py`、`mcp_call_dify.py`、`webhook_post.py`、`export_feedback.py`、`app_types_check.py`)を直下に置く
  - `python/dify_client/`: service-api 章の薄いクライアント(`client.py` / `sse.py` / `stream.py` / `errors.py`)。blocking / streaming の呼び出し、SSE の分解、エラー型をまとめたもの
  - `python/examples/`: `dify_client` を使った service-api 章の実行例(`app_info.py`、`blocking_call.py`、`stream_events.py`、`conversation_files.py`、`stop_and_resubscribe.py`、`human_input_resume.py`、`feedback_and_logs.py`、`blocking_timeout_probe.py`、共通処理 `_common.py`)
  - `python/eval/`: observability 章の回帰評価(`run_eval.py` がテストケース `testcases.yaml` を Service API で流し、`judge.py` が LLM 採点を行う)
  - `python/hybrid/`: limits-migration 章の、Dify とコードを併用する例(`service.py` が LangGraph で分類する FastAPI サービス、`langgraph_calls_dify.py` が LangGraph から Dify の Workflow を呼ぶ側)。依存は `python/hybrid/requirements.txt` で固定
- `tools/`: カスタムツール・MCP サーバー・外部ナレッジ API などの自作サービス
  - `tools/internal_api/`: tools-mcp 章のカスタムツール用 FastAPI(社員照会と IT 機器申請の 2 エンドポイント)。`export_openapi.py` で Dify に貼る `openapi.json` を書き出す
  - `tools/mcp_server/`: tools-mcp 章の外部 MCP サーバー(Streamable HTTP、`get_office_hours` / `lookup_policy` の 2 ツール)
  - `tools/external_kb/`: knowledge 章の External Knowledge API(`/retrieval`、BM25 で `data/policies` を検索)
  - `tools/plugin_minimal/`: tools-mcp 章のツールプラグイン最小例(`office_hours` 1 ツール、`dify plugin package` でパッケージ化する)
- `ops/`: 本番構成・バックアップ・DSL 管理のスクリプトと設定例
  - `ops/env.local.example`: setup 章以降に `docker/.env` へ加えた変更の記録(SSRF プロキシの許可など)
  - `ops/env.production.example`: production-config 章の本番向け環境変数の一覧(値はダミー、置き場所ラベル付き)
  - `ops/docker-compose.override.example.yaml`: production-config 章の MinIO(`STORAGE_TYPE=s3`)への切り替え例
  - `ops/backup.sh`: production-config 章の PostgreSQL ダンプとボリュームの退避スクリプト
  - `ops/langfuse/`: observability 章の Langfuse を Docker Compose で立てる構成(`.env.example` のみコミット)
  - `ops/otel/`: observability 章の OpenTelemetry Collector の構成と Dify 側の設定例
  - `ops/dsl_export_all.sh`: dsl-versioning 章の、ワークスペースの全アプリを DSL にエクスポートするスクリプト
  - `ops/promote.sh`: dsl-versioning 章の、DSL を別アプリへ取り込む(上書きインポート)スクリプト
  - `ops/dsl_diff_filter.py` / `ops/gitattributes.example`: dsl-versioning 章の、座標などの差分ノイズを `git diff` から除くフィルタ
- `data/`: ナレッジに取り込む架空の社内規程
- `verification/`: 章ごとの検証記録(本表の元データ)

## 依存の固定

各 `requirements.txt` の依存はすべて `==` でバージョン固定済み(2026-10-05 確認)。

| ファイル | 依存 | 使う章 |
| --- | --- | --- |
| `python/requirements.txt` | `httpx==0.28.1`、`PyYAML==6.0.2`、`python-dotenv==1.1.1`、`mcp==1.30.0` | 全章の Python スクリプト(`mcp` は tools-mcp 章の `mcp_call_dify.py`、`PyYAML` は observability 章の eval と dsl-versioning 章の diff フィルタ) |
| `tools/internal_api/requirements.txt` | `fastapi==0.142.2`、`uvicorn==0.54.0` | tools-mcp |
| `tools/mcp_server/requirements.txt` | `mcp==1.30.0` | tools-mcp |
| `tools/external_kb/requirements.txt` | `fastapi==0.142.2`、`uvicorn==0.54.0`、`rank-bm25==0.2.2` | knowledge |
| `tools/plugin_minimal/requirements.txt` | `dify_plugin==0.9.1` | tools-mcp |
| `python/hybrid/requirements.txt` | `langgraph==1.2.12`、`langchain-core==1.6.6`、`langchain-ollama==1.1.0`、`httpx==0.28.1`、`python-dotenv==1.1.1`、`fastapi==0.142.2`、`uvicorn==0.54.0` | limits-migration |

FastAPI / uvicorn は全サンプルで 0.142.2 / 0.54.0 に揃えた(`tools/external_kb` は 2026-10-06 に 0.115.6 / 0.34.0 から上げて再検証)。

## 検証状況

結果の見方: 「成功」は API 経由で本文どおりの挙動を確認したもの。「一部」は一部の経路を実行していないもの。「著者確認待ち」は GUI 操作や検証環境を止める必要があり Claude 側で実行していないもの。GUI の画面名・手順は全章で著者確認待ちのため、ここでは省く(`plans/dify-for-code-first-engineers/markers.md` の VERIFY / SCREENSHOT を参照)。

| 章 | サンプル(パス) | 検証日 | 結果 |
| --- | --- | --- | --- |
| introduction | (サンプルなし。図のみ) | 2026-10-03 | 検証対象なし |
| setup | `ops/env.local.example` | 2026-10-03 | 成功(記録ファイル。setup 章時点では `.env.example` との差分なし) |
| setup | `python/smoke_test.py` | 2026-10-03 | 成功(`smoke: chatbot` に blocking で HTTP 200) |
| app-types | `dsl/chatbot-minimal.yml` | 2026-10-03 | 成功(エクスポート → 再インポート `completed` → Service API `mode=chat`。GUI からのインポートは著者確認待ち) |
| app-types | `dsl/workflow-minimal.yml` | 2026-10-03 | 成功(下書き実行、公開 v1、再インポート、Service API `succeeded`) |
| app-types | `python/app_types_check.py` | 2026-10-03 | 成功(`GET /v1/info` と `chat-messages` / `workflows/run` を 2 アプリで実行) |
| workflow | `dsl/support-triage-workflow.yml` | 2026-10-03 | 成功(下書き実行 4 件と Service API 5 件が `succeeded`。`needs_human` が文字列で返る揺れと中国語混入はモデル起因として本文に注記) |
| workflow | `dsl/iteration-batch.yml` | 2026-10-03 | 成功(並列 3 で 4 件を分類、出力順は入力順) |
| workflow | `python/run_workflow.py` | 2026-10-03、2026-10-05 | 成功(2026-10-05 に `partial-succeeded` を警告付きの成功として受け付けるよう修正し、`--input` を追加。workflow-control-flow 章の error-handling で再検証) |
| workflow-control-flow | `dsl/loop-refine.yml` | 2026-10-03 | 成功(下書き 2 件、Service API 1 件。3 周で 8 点に届かず `loop_count` で終了した例を本文に反映) |
| workflow-control-flow | `dsl/error-handling.yml` | 2026-10-03 | 成功(`simulate_error: code` で `node_retry` 2 回 → Fail Branch → `partial-succeeded`。キャンバス表示は著者確認待ち) |
| chatflow | `dsl/support-chatflow.yml` | 2026-10-03 | 成功(同一会話 3 ターンで会話変数の更新を下書き実行と Service API の両方で確認) |
| chatflow | `dsl/support-chatflow-human-input.yml` | 2026-10-03 | 成功(API 経由で `human_input_required` → フォーム送信 → 再開まで確認。Web アプリ上のフォーム表示と Delivery Method は著者確認待ち) |
| chatflow | `python/chat_multiturn.py` | 2026-10-03 | 成功(3 ターン、SSE のイベント順を確認) |
| agent | `dsl/legacy-agent.yml` | 2026-10-03 | 成功(`current_time` を呼んで曜日を回答。blocking は 400。GUI の Agent Settings は著者確認待ち) |
| agent | `dsl/agent-node-workflow.yml` | 2026-10-03 | 一部(ワークフローは全件 `succeeded`。Agent ノードを通った 5 回のうち 2 回でツール未使用、モデル起因として本文に注記。`dependencies` に Agent Strategy プラグインが出ない点を本文に反映) |
| agent | `python/stream_agent.py` | 2026-10-03 | 成功(`agent_thought` の増分表示を 3 回の実行で確認) |
| new-agent | 新 Agent `new-agent: it-request-drafter`(Dify 上。DSL は下記) | 2026-10-05 | 成功(Console API で作成 → 公開 → API 有効化。Agents ページでの表示は著者確認待ち) |
| new-agent | `dsl/new-agent-it-request.yml` | 2026-10-05 | 成功(裏側の app_id でエクスポート、再インポート `completed`、`app_mode: agent`) |
| new-agent | `python/stream_new_agent.py` | 2026-10-05 | 成功(3 ターン。サンドボックスの `shell_run` / `shell_wait` と作業ディレクトリの保持を確認) |
| knowledge | `python/knowledge_ingest.py` | 2026-10-03、2026-10-05 | 成功(規程 6 本をメタデータ付きで投入。区切り文字 `\n\n` と `\n` でチャンク数の違いを確認) |
| knowledge | `python/knowledge_retrieve.py` | 2026-10-05 | 成功(semantic / hybrid は 3 件、メタデータフィルタも有効。`full_text_search` が日本語で 0 件になる原因は未解明、本文に TODO) |
| knowledge | `tools/external_kb/` | 2026-10-06 | 成功(Python 3.12.10 / FastAPI 0.142.2 で再検証。直接呼び出しと Console の `external-hit-testing` の両方で `records` 取得。GUI での登録は著者確認待ち) |
| knowledge | `dsl/rag-chatflow.yml` | 2026-10-05 | 成功(部署フィルタ 2 通りで `retriever_resources` を確認。`dataset_ids` は暗号化のまま再インポートできた) |
| knowledge | `data/policies/` | 2026-10-03 | 成功(5 つのナレッジに取り込み済み) |
| tools-mcp | `tools/internal_api/` | 2026-10-05 | 成功(カスタムツールとして登録、2 ツールを Agent ノードから SSRF プロキシ経由で呼べた。登録ダイアログは著者確認待ち) |
| tools-mcp | `dsl/agent-with-custom-tool.yml` | 2026-10-05 | 成功(照会と申請の 2 ツールを 1 回の実行で正しく呼び分け) |
| tools-mcp | Workflow as Tool と `tools-mcp: tool-node-check`(Dify 上のみ。DSL なし) | 2026-10-05 | 成功(MCP / Workflow / API の 3 種のツールを Tool ノードから順に呼べた。設定 UI は著者確認待ち) |
| tools-mcp | `tools/mcp_server/` | 2026-10-05 | 成功(Dify に `type: mcp` で登録、2 ツールを取り込み。OAuth と Forward user identity は著者確認待ち) |
| tools-mcp | `python/mcp_call_dify.py` | 2026-10-05 | 成功(`initialize` / `tools/list` / `tools/call` が通る。Claude Desktop / Cursor からの接続は著者確認待ち) |
| tools-mcp | `dsl/webhook-triggered-workflow.yml` と `python/webhook_post.py` | 2026-10-05 | 成功(本番 URL に POST → 非同期で `succeeded`。空ボディ 400、テスト URL のリスナー無しは 409) |
| tools-mcp | `tools/plugin_minimal/` | 2026-10-05 | 一部(`dify plugin package` まで成功。Dify へのインストールと実行は未署名のため著者確認待ち) |
| service-api | `python/dify_client/` | 2026-10-05 | 成功(下記 examples の全スクリプトから使用) |
| service-api | `python/examples/app_info.py` | 2026-10-05 | 成功(`/info` / `/parameters` / `/meta`、無効キーの 401、入口違いの 400 / 404) |
| service-api | `python/examples/blocking_call.py` | 2026-10-05 | 成功(Workflow / Chatbot は 200、Legacy Agent は 400 `invalid_param`) |
| service-api | `python/examples/blocking_timeout_probe.py` | 2026-10-05 | 一部(`GUNICORN_TIMEOUT=360` を超える 436 秒の blocking が完走。3600 秒の層は未実測) |
| service-api | `python/examples/stream_events.py` | 2026-10-05 | 成功(Chatflow / Workflow / Chatbot / Legacy Agent のイベント順と `ping` を確認) |
| service-api | `python/examples/conversation_files.py` | 2026-10-05 | 成功(添付有効アプリで upload → 会話 → 名前変更 → 削除。添付無効アプリでは `message_files` が空。GUI での File Upload 有効化は著者確認待ち) |
| service-api | `python/examples/stop_and_resubscribe.py` | 2026-10-05 | 成功(`stop` で `stopped`、切断後の `events` 再購読で完走) |
| service-api | `python/examples/human_input_resume.py` | 2026-10-05 | 成功(フォーム取得 → approve → `events` で再開) |
| service-api | `python/examples/feedback_and_logs.py` | 2026-10-05 | 成功(feedback の付与と取り消し、`/workflows/logs`。`status=partial-succeeded` は 400) |
| deployment-choice | (サンプルなし) | 2026-10-03 | 検証対象なし |
| production-config | `ops/env.production.example` | 2026-10-03 | 成功(作成のみ。変数名と置き場所を `.env.example` / `envs/*.env.example` の grep で確認) |
| production-config | `ops/docker-compose.override.example.yaml` | 2026-10-03 | 一部(`docker compose config` の構文確認のみ。MinIO での起動と `flask migrate-oss` は検証環境を止める必要があり著者確認待ち) |
| production-config | `ops/backup.sh` | 2026-10-03 | 一部(稼働中のバックアップは成功。`STOP_CONTAINERS=1` の経路は著者確認待ち、復元は未検証) |
| observability | `python/eval/`(`run_eval.py` / `judge.py` / `testcases.yaml`) | 2026-10-03、2026-10-05 | 成功(3 回とも 8/8 PASS。judge の採点は 2.75〜3.0 で揺れる) |
| observability | `python/export_feedback.py` | 2026-10-05 | 成功(`feedbacks` / `messages` / `workflow-logs` の 3 サブコマンド) |
| observability | `ops/langfuse/` | 2026-10-05 | 成功(Langfuse 4.50.0 で trace と 6 件の observation を確認。検証後に Dify 側のトレースは無効化済み。GUI パネルは著者確認待ち) |
| observability | `ops/otel/` | 2026-10-05 | 一部(Collector の起動と OTLP 受信は成功。Dify 側 `ENABLE_OTEL=true` は共有 `.env` を変えない方針のため著者確認待ち) |
| dsl-versioning | `dsl/dsl-versioning-secret-env.yml` | 2026-10-03 | 成功(`include_secret=false` で `API_KEY` の `value: ''` を確認。差分ノイズの実測に使用) |
| dsl-versioning | `ops/dsl_export_all.sh` | 2026-10-03 | 一部(エクスポートは成功。`COMMIT=1` の経路は `bash -n` のみ、末尾の difyctl 版は `OPENAPI_ENABLED` / `ENABLE_OAUTH_BEARER` が要るため著者確認待ち) |
| dsl-versioning | `ops/promote.sh` | 2026-10-03 | 成功(上書きインポート、`pending` → `FORCE=1` で confirm、`completed-with-warnings` の 3 経路) |
| dsl-versioning | `ops/dsl_diff_filter.py` と `ops/gitattributes.example` | 2026-10-03 | 成功(座標だけの差分が `git diff` から消え、プロンプト変更は残る) |

## 検証環境に残してあるアプリ

検証用に作ったものは消していない。著者が GUI で画面名・手順を確認する材料にする。`-reimport` は DSL の再インポート確認用で、本体と同じ内容。

### アプリ(Studio)

| 章 | 名前 | app_id | mode |
| --- | --- | --- | --- |
| setup | `smoke: chatbot` | `c57da944-40ea-438f-a567-3d79689d276b` | chat |
| app-types | `app-types: chatbot-minimal` | `e9d27596-d5ad-4b05-ae36-367beb250b56` | chat |
| app-types | `app-types: chatbot-minimal-reimport` | `517f4550-d7ca-48d8-8130-92c149645643` | chat |
| app-types | `app-types: workflow-minimal` | `4945c5b9-cab9-4a21-bc24-49c513d38a54` | workflow |
| app-types | `app-types: workflow-minimal-reimport` | `e3e790e5-3d5f-4fab-a98b-62531904dee3` | workflow |
| workflow | `workflow: support-triage`(Workflow as Tool と MCP Server 公開の元、Langfuse の trace-config あり) | `b8892499-4bc5-4ce1-9f0e-9d59f96f2e88` | workflow |
| workflow | `workflow: support-triage-reimport`(dsl-versioning 章の `promote.sh` で下書きを上書き済み) | `090a48e8-4b17-4a29-b11b-e55bbd148120` | workflow |
| workflow | `workflow: iteration-batch` | `9a7b20fe-40c2-43b8-90a1-d2ccb3a59f0f` | workflow |
| workflow | `workflow: iteration-batch-reimport` | `9594854d-78d4-4268-a151-ba7ecf231e3e` | workflow |
| workflow-control-flow | `workflow-control-flow: loop-refine` | `595e1325-c965-4be6-8eee-d2adc284025f` | workflow |
| workflow-control-flow | `workflow-control-flow: loop-refine-reimport` | `164b985e-f04d-4765-a4f2-e4d5d8f77551` | workflow |
| workflow-control-flow | `workflow-control-flow: error-handling` | `40403ae8-786f-49e0-b126-547cb2bdbe65` | workflow |
| workflow-control-flow | `workflow-control-flow: error-handling-reimport` | `cc0725cf-7393-4add-be8a-0180f2385565` | workflow |
| chatflow | `chatflow: support-chatflow` | `3414a385-8ea3-4277-8785-41178ce96565` | advanced-chat |
| chatflow | `chatflow: support-chatflow-reimport` | `3d9e24ea-ab20-4d1f-b9ab-664db577c7d2` | advanced-chat |
| chatflow | `chatflow: support-chatflow-human-input`(下書き実行が Human Input で一時停止したまま) | `8827f7c8-cc07-4898-922b-80b0ad404c27` | advanced-chat |
| chatflow | `chatflow: support-chatflow-human-input-reimport` | `9fb4123d-bb07-4262-b5c8-4d01497104a2` | advanced-chat |
| agent | `agent: legacy-agent` | `9c3fe484-bb18-464c-84f5-c0511f0cb20e` | agent-chat |
| agent | `agent: legacy-agent-reimport` | `a4661d5a-7c23-49b1-8c67-45f80057827c` | agent-chat |
| agent | `agent: support-triage-agent-node` | `422202af-e531-4cbe-b1ca-eac03a451f44` | workflow |
| agent | `agent: support-triage-agent-node-reimport` | `abe31acc-1887-4cec-b37c-44c5c0b16aff` | workflow |
| new-agent | `new-agent: it-request-drafter`(agent_id `01a10c2e-1caf-750b-afb5-31e0fe902396`。Agents ページ) | `ca3b893c-3397-4ac6-8963-92e10992591d` | agent |
| new-agent | `new-agent: it-request-drafter-reimport`(agent_id `01a10c32-baee-756a-afb0-00f068e54551`、未公開) | `1695179c-01e4-4049-a62e-dddb4a738ffb` | agent |
| knowledge | `knowledge: rag-chatflow` | `37b24e41-5200-4bbc-99af-70be841310dc` | advanced-chat |
| knowledge | `knowledge: rag-chatflow-reimport` | `9c387fe2-b18d-4f0d-98bc-f7b999c01884` | advanced-chat |
| tools-mcp | `tools-mcp: agent-with-custom-tool` | `366e7207-8686-4daf-bca1-cb8d145c1ba5` | workflow |
| tools-mcp | `tools-mcp: agent-with-custom-tool-reimport` | `2c01606c-f6fe-404a-9dbf-cdf328d8afbe` | workflow |
| tools-mcp | `tools-mcp: webhook-triggered` | `3cf247d2-6e67-4762-9a3c-42d130b2b4ee` | workflow |
| tools-mcp | `tools-mcp: webhook-triggered-reimport` | `fa899c31-515a-4fa7-b666-e59672c74623` | workflow |
| tools-mcp | `tools-mcp: tool-node-check`(DSL は examples に無い) | `e38c054b-4163-461f-ad8f-d01237a19905` | workflow |
| service-api | `service-api: long-loop`(Test Run すると約 7 分かかる) | `9ca328b2-ae08-4af0-a9aa-9c350f68bcef` | workflow |
| service-api | `service-api: chatflow-files`(File Upload 有効) | `b40e344f-a8a0-4eae-951f-e763b380e9ed` | advanced-chat |
| dsl-versioning | `dsl-versioning: secret-env`(公開版 v1 / v2) | `03bed196-7e0c-46d7-b984-0bbd5a43fb45` | workflow |
| dsl-versioning | `dsl-versioning: secret-env-reimport` | `b8332834-8418-4dc9-8481-faa53d68e299` | workflow |
| dsl-versioning | `dsl-versioning: secret-env-imported-with-secret`(平文 secret 入りで取り込んだもの) | `fc54d4a8-9874-40ce-a27a-315ac8f3d306` | workflow |
| dsl-versioning | `dsl-versioning: version-pending`(`version: 0.8.0` を FORCE 取り込み) | `64890408-cf53-454b-84ce-b8bd34c088d9` | workflow |
| dsl-versioning | `dsl-versioning: version-warn`(`version: 0.6.0` を取り込み) | `7bfdac6c-66ab-460f-863b-a2d8c199c2d5` | workflow |

### ナレッジ

| 名前 | dataset_id | 内容 |
| --- | --- | --- |
| `knowledge: policies` | `8c3841bf-defe-4c97-a78f-1ce64ccc4f33` | high_quality、`\n\n` / 500 / 50、Hybrid(0.7 : 0.3)、Top K 3。`rag-chatflow` が参照 |
| `knowledge: policies-newline` | `5496c2bd-a680-4529-8f4f-d171a25503bb` | high_quality、既定の `\n` 区切り(チャンク数の比較用) |
| `knowledge: policies-economy` | `db84f2f1-4e24-41a8-884d-5b1ac9e6f9aa` | economy(jieba)、規程 3 本 |
| `knowledge: policies-external` | `a827e8e4-1450-4836-b73f-5d4738333783` | external。External Knowledge API `knowledge: external-kb`(`3ab50ceb-8ba8-4134-b5b6-57796f26bf38`、`http://host.docker.internal:8101`)経由 |
| `knowledge: policies-recheck` | `af92407b-5fe5-41f2-be44-fbd2d4eaf8e6` | high_quality、2026-10-05 に `knowledge_ingest.py` を再実行して作成 |

### ツール・公開設定

| 種別 | 名前 | ID |
| --- | --- | --- |
| カスタムツール(`type: api`) | `internal_hr_it_api`(`get_employee` / `create_it_request`) | `3dcaeafc-d4f7-4ae4-abd1-9b4334da9742` |
| ワークフローツール(`type: workflow`) | `support_triage`(`workflow: support-triage` をツール化) | `899ec520-eec1-4ddf-b6fc-2bf4c1d9ed5e` |
| 外部 MCP サーバー(`type: mcp`) | `internal-helpdesk-mcp`(識別子 `internal-helpdesk`、`http://host.docker.internal:8103/mcp`) | `8158c0c2-cd13-48d5-9c82-4617c2a5e30a` |
| アプリの MCP Server 公開 | `workflow: support-triage` の MCP Server(status `active`) | `625020c1-fbce-4021-9bc2-f078c5eea407` |
| トレース設定 | `workflow: support-triage` の Langfuse trace-config(検証後に `enabled: false`。Langfuse を `ops/langfuse` で起動し直して有効化すれば「In use」を確認できる) | - |

外部サービス(`tools/internal_api` 8102、`tools/mcp_server` 8103、`tools/external_kb` 8101)は手元のプロセスで、Dify 側の登録だけが残る。これらに依存するアプリを GUI で動かすときは先に起動する。Service API キーと MCP / Webhook の URL はリポジトリに置いていない。

## 2026-10-27: 検証モデルを qwen3:8b に変更

- Ollama 0.40.11 の `qwen3:8b` + `nomic-embed-text` で再検証した(Dify 1.17.1、langgenius/ollama 1.0.3)
- qwen3 は思考モードが既定で有効のため、全 DSL のモデル設定に `think: false` を追加した(無いと応答に `<think>` が混ざる)
- 再検証で確認: チャットボット、ワークフロー各種(構造化出力は 3 回連続 bool)、チャットフロー(多ターン、人間の入力)、RAG、レガシー Agent のツール使用、カスタムツール 2 連続呼び出し、hybrid、新 Agent の基本応答
- 未完: webhook 起動の完走(環境要因: 検証中の Docker Desktop 手動停止の後遺症で、非同期実行からの Ollama 接続のみタイムアウト。機構自体は受理→実行→記録まで動作)と、新 Agent のファイル書き込みの完走
