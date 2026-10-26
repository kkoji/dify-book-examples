# 検証記録: limits-migration 章

- 日付: 2026-10-05
- 環境: Dify 1.17.1(セルフホスト、Docker Compose、`docker/.env` は他章と共有のため変更なし。SSRF プロキシは `ops/env.local.example` の許可設定済み)、Ollama `qwen2.5:7b`(プラグイン `langgenius/ollama` 1.0.2)、Python 3.12.10(`python/hybrid/.venv`、langgraph 1.2.12 / langchain-core 1.6.6 / langchain-ollama 1.1.0 / httpx 0.28.1 / python-dotenv 1.1.1 / fastapi 0.142.2 / uvicorn 0.54.0)。共通の `python/.venv` は Console API 操作にだけ使い、依存は追加していない
- 手順は `plans/dify-for-code-first-engineers/writing-guide.md` の「DSL サンプルの作り方」に従った。グラフ JSON は scratchpad の `lm_build.py` で生成し、Console API で下書き保存 → 下書き実行 → 公開 → エクスポート → 再インポート → Service API 実行の順に確認した。HTTP Request ノードの DSL 構造は `vendor/dify/api/tests/fixtures/workflow/http_request_with_json_tool_workflow.yml` と api コンテナ内 graphon 0.7.0 の `nodes/http_request/entities.py`、既定値は `GET /apps/<id>/workflows/default-workflow-block-configs` を根拠にした
- 確認した事実は `research/dify-for-code-first-engineers/limits-migration.md` の「追記(2026-10-05)」に書いた

## サンプル 1: python/hybrid/service.py + dsl/hybrid-workflow.yml(Dify → コード)

- FastAPI + LangGraph の分類サービスをホストの 8104 で起動: `.venv/bin/uvicorn service:app --host 0.0.0.0 --port 8104`。`POST /classify` をホストから叩くと `{"category":"経費","raw":"経費"}`、api コンテナから `-x http://ssrf_proxy:3128` 経由で `host.docker.internal:8104` を叩いても 200
- アプリ名: `limits-migration: hybrid-workflow`、app_id: `2cce609f-9d5d-4392-83ea-6407316eda70`
- 構成(5 ノード): start(`question`)→ http_classify(HTTP Request、`POST http://host.docker.internal:8104/classify`、JSON ボディ `{"question": "{{#start.question#}}"}`、timeout 10/120/30、retry 2 回 1,000 ms)→ parse(Code、`body` を `json.loads` して `category`)→ llm_answer(LLM、種別をシステムプロンプトに差し込む)→ end(`category` / `answer` / `classifier_status`)
- 下書き実行(`POST /apps/<id>/workflows/draft/run`)

| 入力 | 結果 |
| --- | --- |
| 先週の出張で立て替えたタクシー代はどうやって精算すればいいですか。領収書はあります。 | `succeeded`、3.1 秒、`total_steps: 5`、category=経費、`classifier_status: 200`。HTTP Request 0.9 秒、LLM 1.96 秒 |
| ノート PC の電源が入らなくなりました。昨日までは使えていました。 | `succeeded`、2.4 秒、category=IT |

- 公開: `POST /apps/<id>/workflows/publish`(`marked_name: v1`)成功
- エクスポート: `GET /apps/<id>/export?include_secret=false` → `examples/dify-for-code-first-engineers/dsl/hybrid-workflow.yml`(`version: 0.7.0`、ノード 5、依存 `langgenius/ollama:1.0.2@ef203a…`)
- 再インポート: `POST /apps/imports`(`yaml-content`、名前 `limits-migration: hybrid-workflow-reimport`、app_id `ac6bee1b-c535-47fa-a308-f098efbff9d9`)→ `status: completed`、`check-dependencies` → `leaked_dependencies: []`
- Service API(API キーは `POST /apps/<id>/api-keys` で発行、scratchpad の `lm_hybrid_apikey.json`): `POST /v1/workflows/run`(blocking)
  - 「来月の有給休暇を 3 日まとめて取りたいのですが、申請の締め切りはいつですか。」→ `succeeded`、5 ステップ、5.15 秒、category=勤怠
  - 「オフィスの観葉植物の水やり当番は誰が決めていますか。」→ `succeeded`、5 ステップ、2.06 秒、category=その他
- 結果: 成功

## サンプル 2: python/hybrid/langgraph_calls_dify.py(コード → Dify)

- 呼び先: workflow 章の `workflow: support-triage`(app_id `b8892499-4bc5-4ce1-9f0e-9d59f96f2e88`、公開済み)。API キーは scratchpad の `wf_apikey.json` を `python/hybrid/.env`(gitignore 済み)に置いた
- グラフ: `call_dify`(`POST /v1/workflows/run` blocking)→ `route`(`needs_human` の条件付きエッジ)→ `escalate` / `auto_reply`

| 入力 | 結果 |
| --- | --- |
| 先週の出張で立て替えたタクシー代はどうやって精算すればいいですか。領収書はあります。 | `status: succeeded`、category=経費、`needs_human: false` → `auto_reply`。11.8 秒 |
| オフィスの観葉植物の水やり当番は誰が決めていますか。 | `status: succeeded`、category=その他、`needs_human: true` → `escalate`。10.6 秒 |

- 結果: 成功

## サンプル 3: 上限値超過の実験(`WORKFLOW_CALL_MAX_DEPTH`、`.env` 変更なし)

- アプリ名: `limits-migration: depth-probe`、app_id: `ca6d48ee-fb0e-48d2-83ff-c088f0cf5d0b`
- 手順
  1. start → end の Workflow を作って公開(v0)し、`POST /workspaces/current/tool-provider/workflow/create`(`name: depth_probe`、`parameters: [{name: question, form: llm}]`)でツール登録。provider_id `2981d1ed-8ebb-4d81-972b-0d306ee6de19`
  2. 下書きに Tool ノード(`provider_type: workflow`、`provider_id` = 上記、`tool_name: depth_probe`、`question: {{#start.question#}}`)を挟んで公開(v1)
  3. この時点の下書き実行は `succeeded`(0.3 秒、`echo: {"echo": "ping"}`)。ツールは登録時の公開版 v0 に固定されており、`GET .../tool-provider/workflow/get` の `synced: false`
  4. `POST .../tool-provider/workflow/update`(UI の Reconfigure に相当)で `synced: true` にして再度下書き実行
- 結果(想定外): `Max workflow call depth 5 reached.` は出ず、約 0.7 秒に 1 段ずつ入れ子の実行が増え続けた。10 分後の `workflow_runs` は `running` 871 行(`select status, count(*) from workflow_runs where app_id=...`)。api ログに `call depth` の記録なし
- 原因(コード読解): `api/core/app/apps/workflow_app_runner.py` が `DifyGraphInitContext(call_depth=0)` を固定で渡すため、graphon ノードの `workflow_call_depth`(`nodes/base/node.py`)が常に 0。`tool_engine.generic_invoke` で +1、`WorkflowTool._invoke` で +1 されても子実行の `call_depth` は 2 止まりで、`WorkflowEntry.__init__` の `call_depth > 5` に届かない
- 収束: ツールプロバイダを `POST .../tool-provider/workflow/delete` で削除すると、次の段が `Failed to get tool runtime: workflow provider ... not found` で失敗し、約 2.5 秒に 1 段ずつ巻き戻った。最上位の下書き実行は 1,060 秒後に `status: failed`、`total_steps: 2`、`error` は `Failed to invoke tool depth_probe: ` が 880 回連なった文字列。最終的に `workflow_runs` は `succeeded` 2、`failed` 882、`running` 0
- 削除後に Service API(`POST /v1/workflows/run` blocking、キーは scratchpad の `lm_depth_apikey.json`)で実行すると 0.12 秒で `status: failed`、`total_steps: 2`、`error: Failed to invoke tool depth_probe: Failed to get tool runtime: workflow provider ... not found`(循環は起きない)
- 注意: このアプリはツール登録を削除済みなので、著者が GUI で確認するときは Workflow as Tool を登録し直すと再び無限に入れ子になる。確認は「設定 UI で自分自身を選べるか」までにとどめること
- `MAX_VARIABLE_SIZE` は、コード上ノード出力の経路に検査が無く(`api/factories/variable_factory.py` の環境変数・会話変数生成のみ)、`.env` を変えずに再現できる形が見つからなかったため TODO のまま。`WORKFLOW_MAX_EXECUTION_STEPS` は `.env` 変更が要るため未実施

## 調査メモへの追記

- `research/dify-for-code-first-engineers/limits-migration.md` に 7 行追記: 動的グラフが無いことの根拠(graphon `Graph.init` / `GraphEngine` のコマンド種別 / Service API ルート一覧)、`ExecutionLimitsLayer` の中断理由文字列、`MAX_VARIABLE_SIZE` の検査箇所、`WORKFLOW_CALL_MAX_DEPTH` が効かない実機結果と原因、Workflow as Tool の版固定と `synced`、HTTP Request ノードのエディタ初期値、ハイブリッド構成の実機結果

## 本文に残した目印(`books/dify-for-code-first-engineers/limits-migration.md`)

| 行 | 種別 | 内容 |
| --- | --- | --- |
| 34 | TODO(要確認) | `WORKFLOW_MAX_EXECUTION_STEPS` 超過時に Service API の `data.status` と `error` に何が入るか |
| 34 | TODO(要確認) | `WORKFLOW_MAX_EXECUTION_STEPS` が Loop / Iteration の内側とリトライをどう数えるか(観測値を併記) |
| 36 | VERIFY | Workflow as Tool の設定 UI で自分自身のツールを選べるか |
| 38 | TODO(要確認) | ノード出力が `MAX_VARIABLE_SIZE` を超えたときの挙動 |
| 176 | AUTHOR | 移行の判断基準と結論 |
| 198 | AUTHOR | 実運用での所感 |

(行番号は 2026-10-05 時点。SCREENSHOT は無し)

章仕様の「残す目印」のうち「Human Input の一時停止がコンテナ再起動をまたぐか」「#23654 の再現」は本文に TODO を置かず、前者は未検証のまま調査メモの未確認欄に残し、後者は service-api 章の実機(切断後も実行継続)を根拠に「1.17.1 では再現していない」と書いた。

## 分量

- 本文文字数: 5,983 字(`count_chars.py`、コードブロック・コメント・空白を除く。表の文字を含む)。初稿は 9,726 字だったため、仕様の 4,500〜6,000 字に収まるまで削った。削ったのは主に各節の補足文で、上限値の表からは Code の実行時間(workflow 章に記載)と Issue #31253 の行を外した

## 他章への申し送り

- introduction 章: L28 の `TODO(要確認): 実行時にノードやエッジを追加する手段が公式に無いことの一次情報` は、本章と調査メモの追記(graphon `Graph.init` とコマンド種別、API ルート一覧)で根拠が揃ったので外せる
- workflow-control-flow 章: L135 の「超過時の挙動は limits-migration 章で扱います」は本章で受けた。L136 の TODO(`WORKFLOW_CALL_MAX_DEPTH` 超過時のエラーが親のどのノードに出るか)は「1.17.1 では超過しない」という結果になったので書き換えが要る
- tools-mcp 章: L77「入れ子の深さは `WORKFLOW_CALL_MAX_DEPTH`(既定 5)で打ち切られます」は 1.17.1 の実機と食い違う。通読レビューで扱う
- new-agent 章: 新 Agent のモデル呼び出し 500 回の TODO は本章では繰り返さず、new-agent 章の TODO に委ねた
