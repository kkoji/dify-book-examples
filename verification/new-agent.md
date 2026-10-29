# 検証記録: new-agent 章

- 日付: 2026-10-05
- 環境: Dify 1.17.1(セルフホスト、Docker Compose)、Ollama `qwen2.5:7b`(プラグイン `langgenius/ollama` 1.0.2)、Python 3.10 / httpx 0.28.1
- `agent_backend` / `local_sandbox` / `agent_ssrf_proxy` は `docker compose ps` で Up(`local_sandbox` は healthy)。`docker compose logs agent_backend` に実行中の `agent run` / `GET /runs/<id>/events/sse` が流れることを確認。`vendor/dify` の設定は変更していない
- GUI は使わず、Console API(`scratchpad/console.sh`)だけで作成から公開、API 有効化まで行った。GUI の画面手順と画面名は著者確認待ち

## サンプル 1: 新 Agent「new-agent: it-request-drafter」

- agent_id: `01a10c2e-1caf-750b-afb5-31e0fe902396`、裏側の app_id: `ca3b893c-3397-4ac6-8963-92e10992591d`(`mode: agent`)。「Agents」ページに表示されるはず(著者確認待ち)
- 作成: `POST /console/api/agent {"name":"new-agent: it-request-drafter","role":"IT 機器申請の下書きワーカー","description":"…"}` → 201。`enable_site` / `enable_api` は false で作られる
- 設定: `GET /agent/<agent_id>/composer` で既定の `agent_soul` を取り、`prompt.system_prompt` と `model: {plugin_id: langgenius/ollama, model_provider: langgenius/ollama/ollama, model: qwen2.5:7b, model_settings: {temperature: 0.2}}` を入れて `PUT /agent/<agent_id>/composer`(body `{"variant":"agent_app","save_strategy":"save_to_current_version","agent_soul":{…}}`)→ 200、`validation.warnings: []`
- 公開: `POST /agent/<agent_id>/publish {"version_note":"v1 IT request drafter"}` → `result: success`、`active_config_snapshot.version: 2`。`GET /agent/<agent_id>/versions` に display_version 1 として並ぶ
- API 有効化: `POST /agent/<agent_id>/api-enable {"enable_api":true}` → `access_ready: true`、`enabled: true`、`streaming_only: true`、`chat_endpoint: http://localhost/v1/chat-messages`
- API キー: `POST /agent/<agent_id>/api-keys` → `app-` キー(scratchpad の `na_apikey.json`。リポジトリには置かない)
- `GET /v1/info` → `mode: agent`。`response_mode: blocking` → 400 `bad_request`「Agent App only supports streaming response mode.」
- `GET /agent/invite-options` に `agent_kind: dify_agent`、`scope: roster` として表示される(ワークフローの「Invite an Agent」候補になるはず。GUI 表示は著者確認待ち)
- 結果: 成功

## サンプル 2: dsl/new-agent-it-request.yml

- エクスポート: `GET /apps/ca3b893c-3397-4ac6-8963-92e10992591d/export?include_secret=false`(agent_id を渡すと 404 `app_not_found`。裏側の app_id を使う)→ `version: 0.7.0`、`agent.package_ref: agent_1`、`agent_packages.agent_1.{metadata, soul, workspace_skills, omitted_assets}`、`dependencies` に `langgenius/ollama:1.0.2@ef203a…`。秘密情報は含まれない(`credential_ref: null`、`env.secret_refs: []`)
- 再インポート: `POST /apps/imports {"mode":"yaml-content",…,"name":"new-agent: it-request-drafter-reimport"}` → `status: completed`、`app_mode: agent`、app_id `1695179c-01e4-4049-a62e-dddb4a738ffb`(agent_id `01a10c32-baee-756a-afb0-00f068e54551`)、`check-dependencies` → `leaked_dependencies: []`。インポート直後は `active_config_is_published: false`(公開と API 有効化は改めて必要)
- 結果: 成功(仕様では「エクスポートできれば追加」だったので追加した)

## サンプル 3: python/stream_new_agent.py

| # | 入力 | ツール呼び出し | 結果 |
| --- | --- | --- | --- |
| 1 | ノート PC を 1 台申請したいです。用途は新人の開発環境、希望納期は 10 月 20 日、申請者は小島です。 | position 1 `shell_run`(`echo -e … > it_request_draft.md`)、2 `shell_wait`、3 `shell_run`(`cat it_request_draft.md`)、4 ツールなし | 成功。見出し付きの下書きを返した。total_tokens 10,949、latency 104 秒。`echo -e` の `-e` がファイル 1 行目に残り、最終回答の保存先がジョブの `output.log` のパスになっていた(本文の alert に反映) |
| 2 | (同じ conversation_id)はい、保存してください。保存後に it_request_draft.md の中身を cat で表示してください。 | 1 `shell_run`(`cat it_request_draft.md`)、2 ツールなし | 成功。1 回目に書いたファイルがそのまま読めた(会話内でサンドボックスの作業ディレクトリが保持される)。6,562 トークン、47 秒 |
| 3 | モニターを 2 台申請したいです。 | ツールなし(position 1〜3 が進むだけ) | 成功。用途と納期を聞き返した。2,407 トークン、19 秒 |

- SSE の観察: `agent_thought` → `agent_message` が交互に届き、最後に完全な回答の `message` → `message_end`(`metadata.usage` あり、`retriever_resources: []`)。`agent_thought.thought` は常に空文字。`observation` は `<metadata>{job_id, status, exit_code, output_path}</metadata><output>…</output>` の形。`ping` は観測しなかった(10 秒以内に次のイベントが来ていた可能性あり)
- 2 回目の実行時に `message` と `agent_message` の両方を表示して回答が二重に出たため、スクリプトは `message` を最終回答として置き換えるよう修正した(3 回目で確認)
- `GET /agent/<agent_id>/logs` に 3 会話が `status: success`、`source: {type: webapp, id: webapp:<app_id>}` で記録された。Service API 経由でも source は webapp
- 結果: 成功

## 本文に残した目印(`books/dify-for-code-first-engineers/new-agent.md`、2026-10-05 時点の行番号)

| 行 | 種別 | 内容 |
| --- | --- | --- |
| 37 | VERIFY | 作成から公開までの画面手順一式 |
| 42 | VERIFY | Access Point の有効化操作 |
| 44 | SCREENSHOT | Agents ページ |
| 45 | SCREENSHOT | Configure パネル |
| 47 | SCREENSHOT | Build by Chatting |
| 104 | SCREENSHOT | Skills ページ |
| 119 | VERIFY | Agent ノードの New Agent 設定と「Invite an Agent」の表示 |
| 119 | SCREENSHOT | Agent ノードの New Agent 設定 |
| 121 | VERIFY | Chatflow のノード一覧に New Agent が出ないこと |
| 127 | TODO(要確認) | モデル呼び出し 500 回が環境変数で変更できるか |
| 133 | TODO(要確認) | クラウド版での提供状況とプラン制限 |
| 133 | TODO(要確認) | Web アプリでのエンドユーザーのファイル添付可否と上限 |

## 本文の文字数

- 5496 字(`count_chars.py`、コードブロック・コメント・空白を除く)

## 調査メモへの追記

- `research/dify-for-code-first-engineers/agent.md` 末尾に「追記(2026-10-05)」として、Console API のエンドポイント、`agent_soul.model` の形、SSE の実測、DSL の往復、環境変数の置き場所を追加した

## 2026-10-27 qwen3:8b で再検証

- DSL(qwen3:8b 版)を再インポートし、Console API で公開と API 有効化、キー発行(手順は 10/05 と同じ)
- 単純な依頼: 成功。agent_thought と agent_message が交互 → message → message_end の順(本文どおり)。2,780 トークン、20 秒
- ファイル書き込み + cat: 成功。`shell_run` が `echo "## 申請者\n小島\n…" > it_request_draft.md && cat …` を実行し、ファイルは正しい改行で作成された(サンドボックスの sh は echo のエスケープを解釈する)。qwen2.5 の「`-e` が残る」粗さは再現せず。6,626 トークン、41.5 秒
- 注意: ランナーが宙吊りの時間帯は `completion_request_error`(host.docker.internal への read timeout)になる。Ollama 本体の再起動で解消
