# 検証記録: service-api 章

- 日付: 2026-10-05
- 環境: Dify 1.17.1(セルフホスト、Docker Compose、`docker/.env.example` 既定値。api コンテナ `GUNICORN_TIMEOUT=360` / `SERVER_WORKER_CLASS=gevent` / `SERVER_WORKER_AMOUNT=1` / `SERVER_WORKER_CONNECTIONS=10`、nginx `NGINX_PROXY_READ_TIMEOUT=3600s` / `NGINX_PROXY_SEND_TIMEOUT=3600s` / `NGINX_CLIENT_MAX_BODY_SIZE=100M`。`docker inspect` で確認)、Ollama `qwen2.5:7b`(プラグイン `langgenius/ollama` 1.0.2)、Python 3.10.16 / httpx 0.28.1 / python-dotenv 1.1.1(`python/requirements.txt` に追加なし)
- サンプル: `python/dify_client/`(`__init__.py` / `client.py` / `sse.py` / `stream.py` / `errors.py`)と `python/examples/`(`_common.py` / `app_info.py` / `blocking_call.py` / `stream_events.py` / `conversation_files.py` / `stop_and_resubscribe.py` / `human_input_resume.py` / `feedback_and_logs.py` / `blocking_timeout_probe.py`)。実行は `cd python && DIFY_APP_API_KEY=app-... .venv/bin/python examples/<name>.py`。API キーは `console.sh POST /apps/<id>/api-keys` で発行し scratchpad に保管(リポジトリには置かない)
- 既存スクリプト(`run_workflow.py` など)は変更していない

## 対象アプリ

| アプリ名 | app_id | mode | 用途 |
| --- | --- | --- | --- |
| smoke: chatbot | c57da944-40ea-438f-a567-3d79689d276b | chat | blocking / streaming / フィードバック / 添付無効時の挙動 |
| workflow: support-triage | b8892499-4bc5-4ce1-9f0e-9d59f96f2e88 | workflow | info / blocking / streaming / logs |
| chatflow: support-chatflow | 3414a385-8ea3-4277-8785-41178ce96565 | advanced-chat | streaming(終端イベント) |
| chatflow: support-chatflow-human-input | 8827f7c8-cc07-4898-922b-80b0ad404c27 | advanced-chat | Human Input の再開 |
| agent: legacy-agent | 9c3fe484-bb18-464c-84f5-c0511f0cb20e | agent-chat | blocking 400 / agent_thought |
| workflow-control-flow: loop-refine | 595e1325-c965-4be6-8eee-d2adc284025f | workflow | stop / events 再購読 |
| service-api: long-loop(本章で作成) | 9ca328b2-ae08-4af0-a9aa-9c350f68bcef | workflow | blocking タイムアウト実測。loop-refine を `/apps/<id>/copy` し、Loop の `break_conditions` の値を 11(到達不能)、`loop_count` を 15(v1)→ 40(v2)にして公開 |
| service-api: chatflow-files(本章で作成) | b40e344f-a8a0-4eae-951f-e763b380e9ed | advanced-chat | support-chatflow をコピーし `features.file_upload` を `enabled: true, allowed_file_types: [document], allowed_file_extensions: [.TXT, .MD, .PDF], allowed_file_upload_methods: [local_file, remote_url], number_limits: 3` にして公開(v1)。GUI での有効化手順は著者確認待ち |

## 結果

### 入口と認証(`app_info.py`)

- support-triage: `mode=workflow`、`user_input_form` は `question`(paragraph、required)、`file_upload: {enabled: false}`、`system_parameters: {image_file_size_limit: 10, video_file_size_limit: 100, audio_file_size_limit: 50, file_size_limit: 15, workflow_file_upload_limit: 10}`。legacy-agent: `mode=agent-chat`、`tool_icons: ['current_time']`
- 無効キーで `GET /info` → 401 `unauthorized`「Access token is invalid」。Chatbot のキーで `/workflows/run` → 400 `not_workflow_app`。存在しない run ID → 404 `not_found`
- 結果: 成功。API Access 画面の導線は著者確認待ち(VERIFY)

### blocking(`blocking_call.py`)

- support-triage「社内 Wi-Fi に接続できなくなりました。」→ `succeeded`、23.0 秒、6 ステップ、1,170 トークン、outputs `{category: IT, answer, needs_human: false}`
- smoke: chatbot「有給休暇の申請はいつまでに出せばよいですか。」→ `answer`、`conversation_id`、`message_id`、`task_id`、`metadata.usage`(`total_tokens: 99`、`latency: 4.88`)
- legacy-agent → 400 `invalid_param`「Agent Chat App does not support blocking mode」(公式ドキュメントの `bad_request` と異なる。調査メモに追記)。スクリプトは exit 1
- 結果: 成功

### blocking タイムアウト実測(`blocking_timeout_probe.py`、service-api: long-loop)

| 版 | loop_count | 実行 | 結果 |
| --- | --- | --- | --- |
| v1 | 15 | 22:09:49 開始(scratchpad `sa_timeout_probe.py`、httpx read timeout 1800 秒) | HTTP 200、309.1 秒、`status: succeeded`、`elapsed_time: 309.0`、`attempts: 15`(他の検証と同時実行だったため 1 周 約 20 秒) |
| v2 | 40 | 22:16:23 開始(`examples/blocking_timeout_probe.py`) | HTTP 200、436.3 秒、`status: succeeded`、`elapsed_time: 436.2`、`total_steps: 3` |

- 結論: 既定構成では `GUNICORN_TIMEOUT=360` を超えても blocking 応答は切れず完走した(gevent ワーカーのため)。api コンテナのログにも worker timeout の記録なし。次の候補 `NGINX_PROXY_READ_TIMEOUT=3600s` / `APP_MAX_EXECUTION_TIME=3600` は 1 時間級の実行が必要なため未実測(本文は「3600 秒の層」とだけ書き、数値の断定はしていない)
- 注意: `dify_client` の既定 read timeout は 600 秒。これより長い blocking はクライアント側が先に切れる(probe では 1800 秒に上書き)

### streaming(`stream_events.py`)

- support-chatflow(経費の問い合わせ): イベント順 `node_started/finished` ×9 → `message` → `message_end` → `workflow_finished`(`succeeded`、9 ステップ、2,083 トークン)。Question Classifier 12.7 秒 / 999 トークン、Parameter Extractor 7.8 秒 / 891、LLM 10.9 秒 / 193
- support-triage(streaming、scratchpad から直接): 先頭フレームは接続後 0.01 秒の `ping`、途中にも `ping`、`text_chunk` は `from_variable_selector: [normalize, category]` など Output の変数ごとに届く、終端 `workflow_finished`。Question Classifier 966〜968 トークン、LLM 181〜202
- smoke: chatbot(streaming、3 回): 先頭が `ping` だったのは 1 回(LLM が他の実行で混んでいたとき)。他 2 回は 1.6 秒 / 5.1 秒で `message` が先頭。終端 `message_end`
- legacy-agent「今の時刻を教えてください。」: `agent_thought` ×2(`tool` は空)→ `message_end`。qwen2.5:7b がツール呼び出しを文字列として出力し(`elight bulb:current_time{}`)、ツールは実行されなかった(agent 章と同じモデル側の揺れ。本章の主題ではないので本文に載せていない)
- `error` イベントは今回の検証では発生していない(仕様の説明のみ)
- 結果: 成功

### 会話とファイル(`conversation_files.py`、scratchpad の `sa_note.txt` 138 バイト)

- chatflow-files(添付有効): `POST /files/upload` → 201(`id`、`mime_type: text/plain`)。`files: [{type: document, transfer_method: local_file, upload_file_id}]` 付きの 1 ターン目 → 新規会話、2 ターン目は `conversation_id` 継続。`GET /messages` で 1 ターン目の `message_files` に `sa_note.txt`、2 ターン目は空。`POST /conversations/{id}/name` → 新しい名前、`GET /conversations` に反映、`DELETE` → 204
- smoke: chatbot(添付無効 `file_upload: {image: {enabled: false}}`): upload は 201 だが、`files` 付きで送っても 200 で `message_files: []`(黙って捨てられる)。本文の注意書きの根拠
- `auto_generate: true` の名前変更も 200 で LLM が付けた名前が返った
- `conversation_completed`(400)は再現していない(仕様の説明のみ)
- 結果: 成功。Chatflow の Features での File Upload 有効化手順は著者確認待ち(VERIFY)

### 停止と再接続(`stop_and_resubscribe.py`、loop-refine)

- `stop`: 2 つ目の `node_started`(LLM: writer)で `POST /workflows/tasks/{task_id}/stop` → `{result: success}`、`workflow_finished` は `status: stopped`、`total_steps: 2`。`GET /workflows/run/{id}` → `status: stopped`、`error: "Aborted: User requested stop"`
- `resubscribe`: `workflow_started` 受信直後にジェネレータを `close()`(HTTP 切断)→ 5 秒後 `GET /workflow/{run_id}/events?user=...&include_state_snapshot=true` → `workflow_started`(`reason: initial`)→ 実行済みノードの再生 → 残りのノード(Loop 2 周分)→ `workflow_finished`(`succeeded`)。切断しても実行は止まらなかった
- 結果: 成功

### Human Input の再開(`human_input_resume.py`、support-chatflow-human-input)

- 「来週のオフィス移転で、私の席がどこになるか教えてください。」→ `message`(待機中の文)→ `human_input_required` → `workflow_paused`。`GET /form/human_input/{form_token}` → `form_content`(変数解決済み)、`user_actions: [approve, reject]`。`POST` `{user, action: approve, inputs: {comment: ...}}` → 200 `{}`。`GET /workflow/{run_id}/events` → `workflow_started`(`resumption`)→ `human_input_form_filled` → Human Input / Variable Assigner / Answer の `node_finished` → `message_end` → `workflow_finished`(`succeeded`)
- 412 `human_input_form_submitted`(2 回目送信)は再現していない(仕様の説明のみ)
- 結果: 成功

### フィードバックとログ(`feedback_and_logs.py`)

- `feedback`(smoke: chatbot): `POST /messages/{id}/feedbacks` like → `{result: success}`、`GET /app/feedbacks?limit=5` → `{data: [...]}` のみ(`from_source: user`、observability 章の dislike も混在)、`rating: null` で取り消し → success
- `logs`(support-triage): `GET /workflows/logs?limit=5` → `total: 38`、各行 `workflow_run.version`(`2026-10-02 19:36:23.821225`)、`created_by_end_user.session_id`(`service-api-blocking` など)。`GET /workflows/run/{id}` → `inputs` は JSON 文字列(`sys.*` を含む)。`status=partial-succeeded` → 400 `invalid_param`(pydantic literal_error: succeeded / failed / stopped のみ)
- 結果: 成功

### 同時実行(429)

- `APP_MAX_ACTIVE_REQUESTS` は変更していないため `too_many_requests` / `rate_limit_error` は再現していない。本文は仕様の説明のみ

## 本文に残した目印(`books/dify-for-code-first-engineers/service-api.md`)

| 行 | 種別 | 内容 |
| --- | --- | --- |
| 12 | VERIFY | API キー発行の導線(「API Access」→「Backend Service API」→「API Key」→「Create new Secret key」) |
| 13 | SCREENSHOT | アプリの API Access 画面 |
| 55 | TODO(要確認) | 新 Agent(agent モード)の SSE の先頭フレームと `agent_message → message → message_end` の順序 |
| 114 | VERIFY | Chatflow の Features で File Upload(Document)を有効にする手順 |
| 148 | TODO(要確認) | 旧版 `dataset-` 接頭辞のナレッジ API キーが 1.17.1 で有効か(knowledge 章の VERIFY と同件) |

(行番号は 2026-10-05 時点)

## 分量

- 本文文字数: 5,997 字(コードブロック・コメント・空白を除く、`count_chars.py`)。初稿 10,519 字から仕様の 4,500〜6,000 字まで削った

## 調査メモへの追記

- `research/dify-for-code-first-engineers/service-api.md` の事実表に実機確認 8 行を追記(Legacy Agent blocking の `invalid_param`、blocking 436 秒完走、SSE 先頭フレーム、添付無効時の `message_files` 空、stop / events の挙動、`/workflows/logs` の `status` 制約、入口違いのエラーコード、Human Input フォーム API の流れ)。「未確認」の 2 項目に解消状況を付記

## 他章への申し送り

- workflow 章: `run_workflow.py` は `succeeded` 以外を失敗扱いにする。`partial-succeeded` を結果として扱うよう直すか、本章の `blocking_call.py` を参照する注記を入れる(本章の本文では触れた。ファイルは変更していない)
- knowledge 章: `dataset-` 接頭辞の件は本章でも TODO として残した。実機の `POST /apps/<id>/api-keys`(type dataset)は `dataset-` を返しているので、解消時に両章を揃える
- agent 章 / new-agent 章: qwen2.5:7b の Legacy Agent はツール呼び出しを文字列として出力し `agent_thought.tool` が空だった。新 Agent(`agent` モード)の SSE 先頭フレームと `agent_message → message → message_end` の順序は本章では未確認
- limits-migration 章: blocking は 436 秒まで完走し `GUNICORN_TIMEOUT` は効かなかった。「blocking モードの長時間実行」の制約を書くときはクラウド版の 100 秒と、セルフホストでは 3600 秒の層(nginx / APP_MAX_EXECUTION_TIME)が実質の上限になる可能性がある(未実測)と分けて書く
- observability 章: `GET /workflows/logs` の `status` に `partial-succeeded` は指定できない(400)。例外分岐を通った実行を回収するフィルタは別途必要
- 統括: 本章で作ったアプリ `service-api: long-loop`(40 周で約 7 分かかる)と `service-api: chatflow-files` は残してある。long-loop を Studio から Test Run すると長く待つので注意
