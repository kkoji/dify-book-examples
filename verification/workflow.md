# 検証記録: workflow 章

- 日付: 2026-10-03
- 環境: Dify 1.17.1(セルフホスト、Docker Compose)、Ollama `qwen2.5:7b`(プラグイン `langgenius/ollama` 1.0.2)、Python 3.10.16 / httpx 0.28.1
- 手順は `plans/dify-for-code-first-engineers/writing-guide.md` の「DSL サンプルの作り方」に従った。グラフ JSON は scratchpad の `build_triage.py` / `build_iteration.py` で生成し、Console API で下書き保存 → 下書き実行 → 公開 → エクスポート → 再インポート → Service API 実行の順に確認した
- 執筆ガイドとの差分: 1.17.1 の `POST /apps/<id>/workflows/draft` は `environment_variables` キーを受け付けない(`SyncDraftWorkflowPayload` が `extra=forbid` で、環境変数は `environment_variable_patch` で渡す)。本文には影響しないが、ガイドの手順 2 の JSON 例から `environment_variables` を外す必要がある
- 下書き実行 `POST /apps/<id>/workflows/draft/run` は `response_mode: blocking` を渡しても SSE で返る。`workflow_finished` イベントを拾って判定した

## サンプル 1: support-triage-workflow.yml

- アプリ名: `workflow: support-triage`、app_id: `b8892499-4bc5-4ce1-9f0e-9d59f96f2e88`
- 公開: `POST /apps/<id>/workflows/publish`(`marked_name: v1`)成功
- エクスポート: `GET /apps/<id>/export?include_secret=false` → `examples/dify-for-code-first-engineers/dsl/support-triage-workflow.yml`(`version: 0.7.0`、ノード 9、依存は `langgenius/ollama:1.0.2@ef203a…`)
- 再インポート: `POST /apps/imports`(`yaml-content`、名前 `workflow: support-triage-reimport`、app_id `090a48e8-4b17-4a29-b11b-e55bbd148120`)→ `status: completed`、`check-dependencies` の `leaked_dependencies: []`
- 下書き実行(4 件、すべて `succeeded`、6 ステップ、9.7〜12.6 秒)

| 入力 | class_label | outputs |
| --- | --- | --- |
| 先週の出張で立て替えたタクシー代はどうやって精算すればいいですか。領収書はあります。 | 経費 | category=経費、needs_human=false |
| 来月の有給休暇を 3 日まとめて取りたいのですが、申請の締め切りはいつですか。 | 勤怠 | category=勤怠、needs_human=false |
| 社内 Wi-Fi に接続できなくなりました。パスワードを変えた覚えはありません。 | IT | category=IT、needs_human=false |
| オフィスの観葉植物の水やり当番は誰が決めていますか。 | その他 | category=その他、needs_human=true |

- Service API: `examples/dify-for-code-first-engineers/python/run_workflow.py "<問い合わせ>"`(`DIFY_APP_API_KEY` は Console API `POST /apps/<id>/api-keys` で発行、scratchpad の `wf_apikey.json` に保管)
  - 「ノート PC の電源が入らなくなりました。昨日までは使えていました。」→ `succeeded`、14.45 秒、category=IT、needs_human=false
  - 「出張の日当は申請できますか。」→ 4 回実行、すべて `succeeded`、category=経費。ただし 4 回中 2 回、`answer` に中国語などが混じった(例: 「是 ragazzo 出張日當的申請手續…」)。ワークフローとしては成功しており、モデル側の揺れ
- 構造化出力の揺れ(本文の `:::message alert` に反映): LLM ノードの `structured_output` は 4 種別とも JSON の形とキーは安定していたが、`needs_human` が boolean ではなく文字列 `"false"` / `"true"` で返った(下書き実行 4 回すべて)。Code ノード `normalize` が bool に変換しているため、Output の `needs_human` は boolean になっている
- 結果: 成功。GUI の操作手順(本文の番号付き手順)とキャンバス表示は著者確認待ち

## サンプル 2: iteration-batch.yml

- アプリ名: `workflow: iteration-batch`、app_id: `9a7b20fe-40c2-43b8-90a1-d2ccb3a59f0f`
- 公開: `marked_name: v1` 成功。エクスポート → `examples/dify-for-code-first-engineers/dsl/iteration-batch.yml`(ノード 6、Iteration は `is_parallel: true`、`parallel_nums: 3`、`error_handle_mode: continue-on-error`)
- 再インポート: 名前 `workflow: iteration-batch-reimport`、app_id `9594854d-78d4-4268-a151-ba7ecf231e3e` → `completed`、`leaked_dependencies: []`
- 下書き実行(入力 4 行: タクシー代の精算 / 有給の申請期限 / VPN につながらない / 社員食堂のメニュー)
  - 初版プロンプト(「1 語に分類」)では 1 回目に 1 件目が「絹」と返った(モデルの揺れ)。候補 4 つを明示するプロンプトに直して 2 回実行し、いずれも `["経費", "勤怠", "IT", "その他"]`
  - 並列モードでも出力配列は入力と同じ順だった(3 回とも)
- Service API: `run_workflow.py --var questions "…\n…"` → `succeeded`、1.46 秒、4 ステップ、`categories: ["経費", "勤怠", "IT", "その他"]`
- 結果: 成功

## 本文に残した目印(`books/dify-for-code-first-engineers/workflow.md`)

| 行 | 種別 | 内容 |
| --- | --- | --- |
| 39 | VERIFY | 変数選択メニューでのシステム変数の表記(`sys.*` か `userinput.*` か) |
| 42 | VERIFY | 環境変数パネルの LLM 型の項目名と DSL の `value` 構造 |
| 50 | SCREENSHOT | support-triage-workflow インポート直後のキャンバス全体 |
| 61 | VERIFY | GUI 手順 2〜5 の画面上の項目名 |
| 62 | SCREENSHOT | LLM ノードの Structured Output Schema 編集画面 |
| 135 | TODO(要確認) | dify-sandbox:0.2.15 の site-packages のライブラリ一覧 |
| 138 | TODO(要確認) | Code ノードのタイムアウトがどちらで先に切れるか |

(行番号は 2026-10-03 時点。下記の分割で変わる可能性がある)

## 分量と分割

- 本文文字数: 5,182 字(コードブロック・コメント・空白を除く)。全節を入れた初稿は 7,035 字だったため、仕様どおり「基本」で止めた
- 本文から外した「Iteration と Loop」「エラー処理とリトライ」「デバッグ」の 3 節(約 1,900 字、VERIFY 2 件と SCREENSHOT 1 件を含む)は scratchpad の `workflow-control-flow-draft.md` に残してある。続きの章(仮スラッグ `workflow-control-flow`)の素材にできる

## 追記(2026-10-05)

- `python/run_workflow.py` を修正: `partial-succeeded` を失敗扱いにしない(警告を出して `outputs` を表示)。`--input NAME=VALUE` で追加の入力変数を渡せるようにした
- 再検証: `workflow-control-flow: error-handling`(40403ae8-…)に対して `run_workflow.py "ノート PC が起動しません" --input simulate_error=code` → `status: partial-succeeded`、`outputs` に `error_type: CodeExecutionError` と fallback の回答。`simulate_error` 無しでは `succeeded`。いずれも終了コード 0
