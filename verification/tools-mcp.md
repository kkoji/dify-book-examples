# 検証記録: tools-mcp 章

- 日付: 2026-10-05(アプリ・ツールの作成は 2026-10-03、再検証は 2026-10-05)
- 環境: Dify 1.17.1(セルフホスト、Docker Compose)、Ollama `qwen2.5:7b`(プラグイン `langgenius/ollama` 1.0.2)、Agent Strategy プラグイン `langgenius/agent` 0.0.50、Python 3.12.10(`tools/*/.venv`)/ 3.10.16(`python/.venv`、httpx 0.28.1、mcp 1.30.0)
- 追加で導入したプラグイン: なし(ワークスペースには他章の検証で入った `langgenius/maths` 0.0.9 があるが本章では使っていない)
- SSRF プロキシ: `SSRF_PROXY_ALLOW_PRIVATE_IPS` / `SSRF_PROXY_ALLOW_PRIVATE_DOMAINS`(`ops/env.local.example`)を設定済みの環境で、`host.docker.internal:8102` / `:8103` に Dify から到達できた
- 手順は `plans/dify-for-code-first-engineers/writing-guide.md` の「DSL サンプルの作り方」に従った。グラフ JSON は scratchpad の `tm_build.py`、再検証は `tm_verify.py` で実行した

## 作成したリソース(ID)

| 種別 | 名前 | ID |
| --- | --- | --- |
| カスタムツール(`type: api`) | `internal_hr_it_api`(ツール `get_employee` / `create_it_request`) | `3dcaeafc-d4f7-4ae4-abd1-9b4334da9742` |
| ワークフローツール(`type: workflow`) | `support_triage`(workflow 章 `b8892499-…` をツール化) | `899ec520-eec1-4ddf-b6fc-2bf4c1d9ed5e` |
| 外部 MCP サーバー(`type: mcp`) | `internal-helpdesk-mcp`、サーバー識別子 `internal-helpdesk`、URL `http://host.docker.internal:8103/mcp` | `8158c0c2-cd13-48d5-9c82-4617c2a5e30a` |
| アプリの MCP サーバー公開 | `workflow: support-triage`(app_id `b8892499-4bc5-4ce1-9f0e-9d59f96f2e88`)の MCP Server、status `active`、`server_code` 16 文字 | server id `625020c1-fbce-4021-9bc2-f078c5eea407` |
| アプリ | `tools-mcp: agent-with-custom-tool`(workflow) | `366e7207-8686-4daf-bca1-cb8d145c1ba5` |
| アプリ | `tools-mcp: agent-with-custom-tool-reimport` | `2c01606c-f6fe-404a-9dbf-cdf328d8afbe` |
| アプリ | `tools-mcp: webhook-triggered`(workflow、Webhook Trigger 開始) | `3cf247d2-6e67-4762-9a3c-42d130b2b4ee` |
| アプリ | `tools-mcp: webhook-triggered-reimport` | `fa899c31-515a-4fa7-b666-e59672c74623` |
| アプリ | `tools-mcp: tool-node-check`(Tool ノードで MCP / Workflow / API ツールを順に呼ぶ検証用。2026-10-05 に公開) | `e38c054b-4163-461f-ad8f-d01237a19905` |

Service API キーと MCP 公開 URL、Webhook URL は scratchpad(`tm_agent_apikey.json`、`tm_toolcheck_apikey.json`、`tm_mcp.env`、`tm_webhook.env`)に置き、リポジトリには書かない。

## サンプル 1: tools/internal_api(カスタムツール)

- 起動: `INTERNAL_API_KEY=local-dev-key .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8102`(fastapi 0.142.2 / uvicorn 0.54.0)。`export_openapi.py http://host.docker.internal:8102 > openapi.json` で `servers` 付きの仕様を書き出した
- 登録(2026-10-03): `POST /console/api/workspaces/current/tool-provider/api/add`(`schema_type: openapi`、`credentials.auth_type: api_key_header`、ヘッダー `X-API-Key`)。`GET .../tool-provider/api/tools?provider=internal_hr_it_api` で `get_employee` / `create_it_request` の 2 ツールを確認(2026-10-05 も同じ)
- 注意点: `Header` 依存で書いた最初の版は `x-api-key` がツール引数として LLM に見えた。`APIKeyHeader`(`securitySchemes`)に変更後は引数から消えた
- 結果: 成功。GUI の登録ダイアログは著者確認待ち

## サンプル 2: dsl/agent-with-custom-tool.yml

- 作成: `POST /apps`(workflow)→ 下書き保存(User Input → Agent(FunctionCalling、ツール `get_employee` / `create_it_request`、`maximum_iterations: 5`)→ Output)→ 公開 → `GET /apps/<id>/export?include_secret=false`
- エクスポートの観察: `dependencies: []`(Agent ノードは依存抽出の対象外。agent 章と同じ)。ツールに `credential_id` は付かず、`provider_name` に カスタムツールの UUID が入る
- 再インポート: `tools-mcp: agent-with-custom-tool-reimport` → `status: completed`
- Service API(2026-10-05): `POST /v1/workflows/run`、入力「社員 E001 の所属部署を教えてください。あわせてその人にモニターを 1 台申請してください。理由は在宅勤務用です。」→ `succeeded`、3 ステップ、40.5 秒。出力「社員 E001 の所属部署は営業部です。また、在宅勤務用のモニターの申請が受理され、申請番号は REQ-0004 です。…」。FastAPI 側のログに `GET /employees/E001` × 2 と `POST /it-requests` が記録され、2 ツールとも SSRF プロキシ経由で到達した(回答中「申请」の誤字はモデル出力)
- 2026-10-03 の下書き実行(照会のみ / 申請のみ / 両方の 3 パターン)も 3 回とも正しいツールと引数が選ばれた(初回はモデル読み込みを含め 89 秒)
- 結果: 成功

## サンプル 3: Workflow as Tool と tool-node-check

- ワークフローツール登録(2026-10-03): `POST .../tool-provider/workflow/create`(`workflow_app_id` = workflow 章の `b8892499-…`、`name: support_triage`、`parameters: [{name: question, form: llm}]`)
- `tools-mcp: tool-node-check`: User Input(`question` / `topic` / `employee_id`)→ Tool `lookup_policy`(MCP)→ Tool `support_triage`(Workflow)→ Tool `get_employee`(API)→ Output。2026-10-05 に `POST /apps/<id>/workflows/publish` で公開し、Service API `POST /v1/workflows/run`(`topic: expense`、`employee_id: E002`、`question: 経費精算の締め切りはいつですか`)を実行
- 結果: `succeeded`、5 ステップ、53.9 秒。`policy` = MCP サーバーの返した文字列、`triage` = 分類ワークフローの Output を JSON 文字列化したもの(`{"category": "経費", ...}`)、`employee` = FastAPI のレスポンス JSON 文字列。3 種のツールがすべて Tool ノードから呼べた。Workflow as Tool の設定 UI は著者確認待ち

## サンプル 4: tools/mcp_server(外部 MCP サーバー)

- 起動: `.venv/bin/python server.py`(mcp 1.30.0、ポート 8103、Streamable HTTP `/mcp`)
- 登録(2026-10-03): `POST /console/api/workspaces/current/tool-provider/mcp`(`server_url: http://host.docker.internal:8103/mcp`、`server_identifier: internal-helpdesk`)。2 ツール(`get_office_hours` / `lookup_policy`)が取り込まれた
- 2026-10-05: `GET /workspaces/current/tool-providers` に `type: mcp` の登録が残っていることを確認し、`GET .../tool-provider/mcp/update/8158c0c2-…` でツール一覧を再取得 → 2 ツール。`GET .../tool-provider/mcp/tools/<provider_id>` も 200(`provider_id` にサーバー識別子を渡すと 500 になる)
- 結果: 成功。MCP サーバー追加ダイアログ、OAuth、Forward user identity は著者確認待ち

## サンプル 5: python/mcp_call_dify.py(Dify アプリの MCP サーバー公開)

- 公開(2026-10-03): `POST /console/api/apps/b8892499-…/server`(`description`、`parameters: {question: 問い合わせ文(日本語)}`、`status: active`)。URL は `http://localhost/mcp/server/<16 文字>/mcp`(`GET /apps/<id>` の `api_base_url` が `http://localhost/v1` で、web はそこから `/v1` を除いて組み立てる)
- 2026-10-05: `DIFY_MCP_SERVER_URL` を `.env` 相当の環境変数で渡して `mcp_call_dify.py "経費精算の締め切りはいつですか。領収書をなくした場合はどうすればいいですか。"` を実行
  - `initialize`: `server: Dify 1.17.1  protocol: 2025-06-18`、`instructions` = 設定した description
  - `tools/list`: `workflow: support-triage`、`inputSchema: {"type": "object", "properties": {"question": {"description": "問い合わせ文(日本語)", "type": "string"}}, "required": ["question"]}`
  - `tools/call`: `isError: False`、`text` と `structuredContent` の両方に `{"category": "経費", "answer": "経費精算の締め切りは毎月25日です。…", "needs_human": false}`
- 結果: 成功。Claude Desktop / Cursor からの接続は著者確認待ち

## サンプル 6: dsl/webhook-triggered-workflow.yml と python/webhook_post.py

- 作成(2026-10-03): workflow 章のアプリを `POST /apps/<id>/copy` で複製し、`start` を `trigger-webhook`(`method: POST`、`content_type: application/json`、`body: [{name: question, type: string, required: true}]`、`async_mode: true`、`status_code: 200`)に置き換え、Question Classifier と LLM の参照を `{{#webhook.question#}}` に変更。公開後にエクスポート。再インポート `tools-mcp: webhook-triggered-reimport` → `completed`
- URL: `GET /console/api/apps/<id>/workflows/triggers/webhook?node_id=webhook` → `webhook_url: http://localhost/triggers/webhook/<24 文字>`、`webhook_debug_url: http://localhost/triggers/webhook-debug/<24 文字>`(`TRIGGER_URL` は既定の `http://localhost`)。エクスポートした DSL では `webhook_url` / `webhook_debug_url` が空
- 2026-10-05: `webhook_post.py "ノート PC の電源が入りません。昨日までは使えていました。"` → `status: 200`、`body: {"status":"success","message":"Webhook processed successfully"}`。`GET /apps/<id>/workflow-app-logs` の最新行は `triggered_from: webhook`、`created_from: service-api`、最初は `running`、約 1 分後に `succeeded`(54.2 秒)、`outputs: {"category": "IT", "answer": "一度電源ボタンを長押ししてから再起動試みてください。…", "needs_human": false}`
- 異常系: ボディ `{}` を POST → 400。テスト用 URL(`webhook-debug`)にリスナー無しで POST → 409
- 結果: 成功。Webhook Trigger ノードの設定パネルは著者確認待ち

## サンプル 7: tools/plugin_minimal(ツールプラグインの最小例)

- `dify plugin init --quick --category tool --language python` の雛形(2026-10-03)を元に、ツール `office_hours` を 1 つだけ持たせた。SDK `dify_plugin==0.9.1`
- `dify` CLI: Homebrew(`brew install langgenius/dify/dify`)は Command Line Tools が古いというエラーで失敗したため、dify-plugin-daemon Releases の `dify-plugin-darwin-arm64`(v0.6.10)を scratchpad に置いて使った
- 2026-10-05: `dify plugin package ./plugin_minimal -o <scratchpad>/office_hours.difypkg` → `plugin packaged successfully`(9,837 バイト、未署名)
- 結果: パッケージ化まで成功。Dify へのインストール(`FORCE_VERIFYING_SIGNATURE=false` か第三者署名が必要)と実行は著者確認待ち

## 本文に残した目印(`books/dify-for-code-first-engineers/tools-mcp.md`、2026-10-05 時点の行番号)

| 行 | 種別 | 内容 |
| --- | --- | --- |
| 11 | SCREENSHOT | Integrations > Tools のツール一覧(4 種類のタブ) |
| 21 | AUTHOR-REVIEW | HTTP Request ノードとツールの使い分け |
| 43 | VERIFY | カスタムツール作成ダイアログの項目の並びと API キー入力欄の名前 |
| 44 | SCREENSHOT | カスタムツール作成ダイアログ(openapi.json を貼って 2 ツールが解析された状態) |
| 75 | VERIFY | "Workflow as Tool" のカードの場所とパラメータ設定の項目名 |
| 85 | SCREENSHOT | MCP サーバー追加ダイアログ |
| 88 | TODO(要確認) | Forward user identity で転送される値の形式 |
| 96 | SCREENSHOT | Access Point タブの MCP Server カード |
| 101 | VERIFY | Claude Desktop / Cursor からの接続 |
| 106 | VERIFY | プラグインページの日本語メニュー名とローカル導入時の文言 |
| 109 | TODO(要確認) | 第三者署名検証に必要な daemon / CLI の最低バージョン |
| 132 | SCREENSHOT | Webhook Trigger ノードの設定パネル |
| 142 | AUTHOR | 実運用での所感 |

## 分量

- 本文文字数: 5,959 字(コードブロック・コメント・空白を除く。仕様の 5,000〜6,000 字に収まる)。前任の下書き 8,707 字から、プラグイン開発の節(最小例と公式リンクに縮約)、トリガーの節(Webhook のみ)、HTTP Request ノードの上限値(limits-migration 章へ委譲)、各節の重複説明を削った

## 他章への申し送り

- limits-migration 章: 本文で「HTTP Request ノードの上限値は limits-migration 章にまとめます」と書いた。`HTTP_REQUEST_NODE_MAX_TEXT_SIZE` / `MAX_BINARY_SIZE`、タイムアウト上限(10 / 600 / 600 秒)、リトライ最大 10 回、`API_TOOL_DEFAULT_*_TIMEOUT`、`WORKFLOW_CALL_MAX_DEPTH`、`WEBHOOK_REQUEST_BODY_MAX_SIZE` を表に含めてほしい
- dsl-versioning 章: カスタムツール(`type: api`)とワークフローツールは `provider_id` が UUID で、別ワークスペースではそのまま解決できない。Webhook Trigger の `webhook_url` はエクスポートで空になりインポート先で再採番される
- service-api 章: 本章の MCP 公開 URL と Webhook URL は `python/.env.example` に `DIFY_MCP_SERVER_URL` / `DIFY_WEBHOOK_URL` として追記した。`requirements.txt` の `mcp==1.30.0` も本章の追記
- new-agent 章 / agent 章: Agent ノードに MCP ツールを持たせる検証は行っていない(カスタムツールのみ)

## 2026-10-27 qwen3:8b 再検証(webhook は未完)

- カスタムツール: 成功。社員 E001 の照会 → ノート PC 申請(REQ-0001)が 1 文の依頼で 2 ツール連続で呼ばれた(qwen2.5 と同じ挙動)
- MCP 経由の呼び出し: 未再検証(機構はモデル非依存)
- Webhook 起動: 未完。受理(200)→ 実行キュー投入 → ログ記録までは動くが、この日の検証環境では実行が LLM 呼び出しで止まり続けた。原因は Ollama ランナーの宙吊り(検証中の Docker Desktop 手動停止の後遺症で、タイムアウト切断のたびに再発)と、終盤は実行が開始されない状態(スタック再作成でも解消せず、原因未特定)。機構自体は 10/05 に qwen2.5 で完走済み
- 残検証: 環境がきれいな状態(Mac または Ollama と Docker の再起動直後)で webhook を 1 回流し、succeeded を確認する

<!-- VERIFY: 著者が環境のきれいな日に webhook の完走を 1 回確認する(手順: POST http://localhost/triggers/webhook/<id> に {"question": "..."}。結果はアプリのログ画面) -->
