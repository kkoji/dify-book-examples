# 検証記録: agent 章

- 日付: 2026-10-03
- 環境: Dify 1.17.1(セルフホスト、Docker Compose)、Ollama `qwen2.5:7b`(プラグイン `langgenius/ollama` 1.0.2、`tool-call` / `multi-tool-call` 付きで登録済み)、Agent Strategy プラグイン `langgenius/agent` 0.0.50(導入済み)、Python 3.10.16 / httpx 0.28.1
- 追加で導入したプラグイン: なし。ツールは 1.17.1 に組み込みで入っている `builtin` 提供元 `time` の `current_time` を使った(`GET /workspaces/current/tools/builtin` で `time` / `audio` / `code` / `webscraper` が確認できる)。ワークスペースには `langgenius/maths` 0.0.9(他章の検証で導入されたもの)も入っているが本章では使っていない
- 手順は `plans/dify-for-code-first-engineers/writing-guide.md` の「DSL サンプルの作り方」に従った。Agent ノードのグラフ JSON は scratchpad の `build_agent_wf.py` で生成した

## サンプル 1: legacy-agent.yml(Legacy Agent)

- アプリ名: `agent: legacy-agent`、app_id: `9c3fe484-bb18-464c-84f5-c0511f0cb20e`(`mode: agent-chat`)
- 作成: `POST /apps {"mode":"agent-chat"}` → `POST /apps/<id>/model-config` で `agent_mode: {enabled: true, strategy: function_call, max_iteration: 5, tools: [time/current_time]}` と `pre_prompt` を設定。ツールの固定値は `format: '%Y-%m-%d %H:%M:%S (%A)'`、`timezone: Asia/Tokyo`
- エクスポート: `GET /apps/<id>/export?include_secret=false` → `examples/dify-for-code-first-engineers/dsl/legacy-agent.yml`(`dependencies` は `langgenius/ollama:1.0.2@ef203a…` のみ。組み込みツール `time` はプラグインではないので依存に出ない)
- 再インポート: `POST /apps/imports`(名前 `agent: legacy-agent-reimport`、app_id `a4661d5a-7c23-49b1-8c67-45f80057827c`)→ `status: completed`、`GET /apps/imports/<app_id>/check-dependencies` → `leaked_dependencies: []`
- Service API(`python/stream_agent.py`、API キーは scratchpad の `agent_legacy_apikey.json`)
  - `blocking` を送ると 400 `invalid_param`「Agent Chat App does not support blocking mode」(本文の記述どおり)
  - 1 回目(`format` に `%A` なし): 「今日は何曜日ですか。今から経費精算の申請を出しても今週分として受け付けてもらえますか。」→ 反復 1 で `current_time` 呼び出し(`observation={"current_time": "2026-10-03 09:17:20"}`)、反復 2 で「今日は月曜日です」と回答。実際は土曜日で、モデルが日付から曜日を誤推測した(本文の alert に反映)
  - 2 回目(`%A` 追加後): 同じ問い → 反復 1 で `current_time`(`2026-10-03 09:18:07 (Saturday)`)、反復 2 で「今日は土曜日です。…今週分は来週に移ります」。total_tokens 660、latency 2.9 秒。回答中の「週末に受け付け」はモデルの創作で、プロンプトには書いていない
  - 3 回目(同じ `conversation_id` で継続): 「さっき教えてもらった曜日をもう一度」→ ツールを使わず「今日は土曜日です。」(履歴が効いている)
  - SSE の観察: 同じ `position` の `agent_thought` が思考 → ツール入力 → 結果と内容が増えるたびに再送される(1 反復で最大 3 回)。`stream_agent.py` は position ごとに増分だけ表示する。最後に完全な回答の `message` → `message_end` の順で届いた
- 結果: 成功。GUI(Agent Settings、Maximum Iterations の既定表示 10)は著者確認待ち

## サンプル 2: agent-node-workflow.yml(Agent ノード入り Workflow)

- アプリ名: `agent: support-triage-agent-node`、app_id: `422202af-e531-4cbe-b1ca-eac03a451f44`
- 作成: `POST /apps/b8892499-4bc5-4ce1-9f0e-9d59f96f2e88/copy` で workflow 章のアプリを複製し、`llm_it` を削除して `agent_it`(type `agent`、`langgenius/agent/agent` の `function_calling`、ツール `time/current_time`、`maximum_iterations: 3`、`memory.window.enabled: false`)と `wrap_it`(Code。`text` を `{category, answer, needs_human}` の object に整える)を追加。Variable Aggregator の `[llm_it, structured_output]` を `[wrap_it, result]` に差し替え。ノードは start / classifier / llm_expense / llm_attendance / agent_it / wrap_it / llm_other / aggregator / normalize / end の 10 個
- 下書き保存: `POST /apps/<id>/workflows/draft` 成功(`environment_variables` は渡さない)
- 公開: `POST /apps/<id>/workflows/publish`(`marked_name: v1`)成功
- エクスポート: → `examples/dify-for-code-first-engineers/dsl/agent-node-workflow.yml`(`version: 0.7.0`)。**`dependencies` に `langgenius/agent` が含まれず Ollama のみ**。`vendor/dify/api/services/app_dsl_service.py` の依存抽出が Tool / LLM / Parameter Extractor / Knowledge Retrieval ノードだけを対象にしているため(本文と research/agent.md に追記)
- 再インポート: 名前 `agent: support-triage-agent-node-reimport`、app_id `abe31acc-1887-4cec-b37c-44c5c0b16aff` → `completed`、`leaked_dependencies: []`(Agent Strategy プラグイン導入済みの環境なので不足は検出されない。未導入環境での挙動は未確認)
- 下書き実行(`POST /apps/<id>/workflows/draft/run`、SSE で `workflow_finished` を判定)

| # | 入力 | 分類 | Agent のツール呼び出し | 結果 |
| --- | --- | --- | --- | --- |
| 1 | 社内 Wi-Fi に接続できなくなりました。今からヘルプデスクに電話しても受け付けてもらえますか。(受付時間を Instruction に書く前) | IT | ROUND 1 で `current_time` → `2026-10-03 09:19:04 (Saturday)`、ROUND 2 で回答 | succeeded、17.4 秒、7 ステップ。「はい、受付可能です」(受付時間の情報がないため) |
| 2 | 同上(Instruction に「平日 9:00〜18:00」を追記後) | IT | ROUND 1 で `current_time`、ROUND 2 で回答 | succeeded、7.7 秒。「今週は土曜日で、受付時間外です。月〜金の 9 時から 18 時まで…」 |
| 3 | ノート PC の電源が入りません。昨日までは使えていました。 | IT | 呼ばず(「現在の時間をお聞かせいただけますか?」と聞き返した) | succeeded、6.3 秒。ワークフローとしては成功だがツール未使用 |
| 4 | 来月の有給休暇を 3 日まとめて取りたいのですが、申請の締め切りはいつですか。 | 勤怠 | (Agent ノードを通らない) | succeeded、12.9 秒、6 ステップ、needs_human=true。他分岐が壊れていないことを確認 |

- Service API(`python/run_workflow.py`、API キーは scratchpad の `agent_wf_apikey.json`): 「VPN につながりません。今日中にヘルプデスクに電話で相談できますか。」→ `succeeded`、22.9 秒、7 ステップ、category=IT。ただし Console の node-executions で確認すると Agent ノードは ROUND 1 でツールを呼ばずに回答していた(`tool_responses: []`)
- ツール呼び出しの安定性: Agent ノードを通った 5 回(下書き 3 回 + 初版 1 回 + API 1 回)のうち 2 回でツール未使用。本文の `:::message alert` に反映
- 出力変数の観察: `node_finished.outputs` のキーは `text` / `usage` / `files` / `json`。`text` は各 ROUND の LLM テキストが改行で連結される(例: 「現在時刻を確認してからお答えします。\n\n今週は土曜日で…」)。`json` には ROUND ごとの `llm_response` と `tool_responses` が入る。SSE には `agent_log` イベント(label が `ROUND 1` / `qwen2.5:7b Thought` / `CALL current_time`)が流れた
- 結果: 成功(ツール呼び出しの揺れはモデル起因として本文に注記)。GUI 手順とキャンバス表示は著者確認待ち

## サンプル 3: python/stream_agent.py

- 上記サンプル 1 の 3 回の実行で検証済み。`DIFY_APP_API_KEY` と `DIFY_API_BASE` は `.env` から読む(`.env.example` は既存のものを流用)。追加の依存なし

## 本文に残した目印(`books/dify-for-code-first-engineers/agent.md`、2026-10-03 時点の行番号)

| 行 | 種別 | 内容 |
| --- | --- | --- |
| 19 | VERIFY | Legacy Agent の作成導線(「More basic app types」→ Agent)と Agent Settings の項目 |
| 21 | SCREENSHOT | Legacy Agent の Agent Settings ダイアログ |
| 27 | VERIFY | Maximum Iterations の既定表示が 10 か |
| 70 | VERIFY | Agent ノード設定パネルの項目名と並び |
| 72 | SCREENSHOT | Agent ノードの設定パネル |
| 74 | VERIFY | Memory の項目名(Window Size)と単位 |
| 76 | VERIFY | 変数選択メニューに出る Agent ノードの出力変数名(実行結果では text / json / files / usage) |
| 80 | SCREENSHOT | agent-node-workflow をインポートしたキャンバス |
| 90 | VERIFY | GUI 手順 2〜3 の画面上の項目名 |
| 128 | VERIFY | ツール追加ダイアログでの MCP ツールの見え方 |

TODO(要確認)は残していない。

## 分量

- 本文文字数: 5,461 字(コードブロック・コメント・空白を除く。仕様の 4,000〜5,500 字に収まる)

## 他章への申し送り

- new-agent 章: 本章の「どこまで制御できるか」は Legacy Agent / Agent ノードの話に限定した。新 Agent との比較はそちらで
- tools-mcp 章: `agent-node-workflow.yml` の `agent_it` が持つツール `time/current_time` を社内 API のカスタムツールに差し替える前提で本文を書いた。ツールの `settings`(form パラメータ)は `{name: {value: {type: constant, value: ...}}}` の形
- dsl-versioning 章: Agent ノードの戦略プラグインは `dependencies` に出ない(上記)。環境間移行の手順に「Agent Strategy プラグインを先に入れる」を含める
- limits-migration 章: Issue #38912(Chatflow 内 Agent ノードでの API ハング)は本章では言及のみ
