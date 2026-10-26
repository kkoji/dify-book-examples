# 検証記録: chatflow 章

- 日付: 2026-10-03
- 環境: Dify 1.17.1(セルフホスト、Docker Compose)、Ollama `qwen2.5:7b`(プラグイン `langgenius/ollama` 1.0.2)、Python 3.10 / httpx 0.28.1
- 手順は `plans/dify-for-code-first-engineers/writing-guide.md` の「DSL サンプルの作り方」に従った。グラフ JSON は scratchpad の `build_chatflow.py` で生成し、Console API で下書き保存 → 下書き実行(`POST /apps/<id>/advanced-chat/workflows/draft/run`、`query` と `conversation_id` を渡す)→ 公開 → エクスポート → 再インポート → Service API 実行の順に確認した
- DSL の根拠: 会話変数と Answer / Variable Assigner の構造は `vendor/dify/api/tests/fixtures/workflow/basic_chatflow.yml` と `test_streaming_conversation_variables.yml`、Human Input は `api/core/workflow/nodes/human_input/entities.py` と `web/app/components/workflow/nodes/human-input/{default,types}.ts`、LLM の `memory` は graphon `prompt_entities.MemoryConfig`(`window.enabled` / `window.size` / `query_prompt_template`)。`default-workflow-block-configs` には llm / question-classifier などの既定しかなく、answer / assigner / human-input の既定は含まれていなかった

## サンプル 1: support-chatflow.yml(会話変数 + Memory + 複数 Answer)

- アプリ名: `chatflow: support-chatflow`、app_id: `3414a385-8ea3-4277-8785-41178ce96565`
- ノード 9: start / classifier(Question Classifier、`sys.query`)/ extract(Parameter Extractor、`department`、function_call)/ if_dept(IF/ELSE `not empty`)/ assign_dept / assign_state(`category` over-write、`turn_count` `+=` 1)/ answer_ack / llm(Memory `window.enabled: true, size: 10`)/ answer_main。会話変数は category(string)/ department(string)/ turn_count(number)
- 公開: `POST /apps/<id>/workflows/publish`(`marked_name: v1`)成功
- エクスポート: `GET /apps/<id>/export?include_secret=false` → `dsl/support-chatflow.yml`(`version: 0.7.0`、依存は `langgenius/ollama:1.0.2@ef203a…`)
- 再インポート: `POST /apps/imports`(名前 `chatflow: support-chatflow-reimport`、app_id `3d9e24ea-ab20-4d1f-b9ab-664db577c7d2`)→ `status: completed`、`leaked_dependencies: []`
- 下書き実行(同一 conversation_id `73dc8efa-…` で 3 ターン、すべて `succeeded`、23〜36 秒)

| ターン | 発話 | class_label | extract.department | answer_ack |
| --- | --- | --- | --- | --- |
| 1 | 経理部の田中です。先週の出張で立て替えたタクシー代はどうやって精算すればいいですか。 | 経費 | 経理部(if_dept true → assign_dept 実行) | 【種別: 経費 / 部署: 経理部 / 1 回目の質問】 |
| 2 | 領収書をなくした場合はどうすればいいですか。 | 経費 | 空(if_dept false) | 【種別: 経費 / 部署: 経理部 / 2 回目の質問】 |
| 3 | ところで来月の有給休暇の申請締め切りはいつですか。 | 勤怠 | 空 | 【種別: 勤怠 / 部署: 経理部 / 3 回目の質問】 |

- Service API: `DIFY_APP_API_KEY=<app-…> python chat_multiturn.py`(キーは `POST /apps/<id>/api-keys` で発行、scratchpad の `cf_key_<app_id>.json` に保管)。新しい会話 `ffe7f2f4-…` で 3 ターンとも成功し、answer_ack の表示は下書き実行と同じ(1 → 2 → 3 回目、部署は経理部のまま、3 ターン目で種別が勤怠)。各ターンの SSE イベントの出現順は `workflow_started node_started node_finished message message_end workflow_finished` で、`message_end` の後に `workflow_finished` が届くことを確認した
- 所見: LLM の回答内容は qwen2.5:7b の揺れがある(2 ターン目の「経理部の皆様」、3 ターン目の架空の締切日)。本文には回答内容を載せていない
- 結果: 成功。GUI の会話変数パネルと Memory の Window Size 既定値は著者確認待ち

## サンプル 2: support-chatflow-human-input.yml(Human Input、Webapp 配信)

- アプリ名: `chatflow: support-chatflow-human-input`、app_id: `8827f7c8-cc07-4898-922b-80b0ad404c27`
- ノード 13: start / classifier / assign_cat / llm_draft(構造化出力 `{answer, needs_human}`、Memory)/ normalize(Code、needs_human を bool 化)/ if_human(`is true`)/ answer_wait / human_input(webapp、approve / reject、`comment` Paragraph、timeout 1 day)/ assign_confirmed(`confirmed` set true)/ answer_approved / answer_rejected / answer_timeout(`__timeout`)/ answer_direct。会話変数は category(string)/ confirmed(boolean)
- 公開: `marked_name: v1` 成功。エクスポート → `dsl/support-chatflow-human-input.yml`。再インポート(名前 `chatflow: support-chatflow-human-input-reimport`、app_id `9fb4123d-bb07-4262-b5c8-4d01497104a2`)→ `completed`、`leaked_dependencies: []`
- 下書き実行
  - 「社内 Wi-Fi に接続できなくなりました…」→ IT、`needs_human` が文字列 `"false"` で返り normalize が false に変換、if_human false → answer_direct、`succeeded`(7 ステップ)
  - 「オフィスの観葉植物の水やり当番は…」→ その他、`needs_human: "true"` → true、answer_wait の後 `human_input_required`(`form_token`、`display_in_ui: true`、`expiration_time` は約 24 時間後)と `workflow_paused`(`status: paused`、`paused_nodes: ["human_input"]`)が届いて停止。この下書き実行の一時停止はそのまま残してある(著者が GUI で確認する材料)
- Service API(scratchpad `hi_api_test.py`、`POST /v1/chat-messages` streaming)
  - 1 回目「観葉植物の水やり当番」は `needs_human: false` で止まらず完走した(モデルの揺れ)。2 回目「来週のオフィス移転で、私の席がどこになるか教えてください。」で停止した
  - 停止時のイベント順: `workflow_started node_started node_finished message human_input_required workflow_paused`。`human_input_required.data` に `form_token`、`approval_channels: ["console"]`、`expiration_time`、`workflow_paused.data.status: paused`
  - `GET /v1/form/human_input/{form_token}` → 200、`form_content`(変数解決済み)、`inputs`、`user_actions`、`expiration_time`
  - `POST /v1/form/human_input/{form_token}` body `{"user": "...", "inputs": {"comment": "総務部に確認済みです。"}, "action": "approve"}` → 200 `{}`
  - `GET /v1/workflow/{workflow_run_id}/events?user=...` → `workflow_started`(`reason: resumption`)→ `human_input_form_filled` → human_input `node_finished`(outputs: `comment`、`__action_id: approve`、`__action_value: 承認して返信`、`__rendered_content`)→ assign_confirmed → answer_approved → `message_end` → `workflow_finished`(`succeeded`、`outputs.answer` は answer_wait と answer_approved の連結)
  - `GET /v1/messages?conversation_id=...` で、該当メッセージの `answer` が両 Answer の連結、`status: normal`
- 結果: 成功(API 経由)。Web アプリ上でフォームが表示されボタンで再開できること、Delivery Method の選択肢、タイムアウト初期値は著者確認待ち

## 本文に残した目印(`books/dify-for-code-first-engineers/chatflow.md`)

| 行 | 種別 | 内容 |
| --- | --- | --- |
| 14 | VERIFY | 「Switch to Workflow Orchestrate」のメニュー位置 |
| 29 | SCREENSHOT | support-chatflow インポート直後のキャンバス全体 |
| 36 | VERIFY | 会話変数パネルの開き方と項目名 |
| 37 | SCREENSHOT | 会話変数パネル(category / department / turn_count) |
| 97 | VERIFY | Memory の Window Size 既定値(web コードでは 50)とスライダー上限 |
| 98 | TODO(要確認) | window 無効時の履歴トークン上限(max_token_limit 2000 の適用箇所) |
| 119 | VERIFY | Human Input のタイムアウト初期値(ドキュメント 3 日 / API 既定 36 時間。web の default.ts は 3 day) |
| 120 | VERIFY | Delivery Method に Slack / Discord / Teams が出るか |
| 121 | SCREENSHOT | Human Input ノードの設定パネル |
| 149 | VERIFY | Web アプリでフォーム表示と「承認して返信」での再開 |
| 150 | SCREENSHOT | Web アプリでフォームが表示された画面 |
| 157 | VERIFY | ログの会話詳細で Variable Assigner の入力に会話変数が見えるか |

## 分量

- 本文文字数: 4,989 字(コードブロック・コメント・空白を除く。`count_chars.py` で計測)

## 他章への申し送り

- service-api 章: Human Input の Service API は上記のとおり `GET/POST /v1/form/human_input/{form_token}` → `GET /v1/workflow/{run_id}/events` で再開まで通った。`human_input_required.data.approval_channels` に `console` が入る点(Service API 起動でも console 側の受信者が併設される)は research 未記載なので、書くなら調査メモに追記が必要
- limits-migration 章: 「一時停止は Human Input ノードのみ」の伏線を本章の末尾に置いた
- 構造化出力の `needs_human` が文字列で返る揺れは Chatflow でも同じ(下書き実行・API とも)。Code ノードで吸収する設計を踏襲した
- scratchpad の `run_chat_draft.py` は knowledge 章のエージェントに上書きされたため、本章の下書き実行結果は `cf_run{1,2,3}.txt` / `cfh_run{1,2}.txt` / `cf_api_run.txt` / `cfh_api_run.txt` に残してある
