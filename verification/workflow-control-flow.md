# 検証記録: workflow-control-flow 章

- 日付: 2026-10-03
- 環境: Dify 1.17.1(セルフホスト、Docker Compose)、Ollama `qwen2.5:7b`(プラグイン `langgenius/ollama` 1.0.2)、Python 3.10.16 / httpx 0.28.1
- 手順は `plans/dify-for-code-first-engineers/writing-guide.md` の「DSL サンプルの作り方」に従った。グラフ JSON は scratchpad の `build_loop.py` / `build_error.py`(後者は `dsl/support-triage-workflow.yml` を読み込んで改変)で生成し、Console API で下書き保存 → 下書き実行 → 公開 → エクスポート → 再インポート → Service API 実行の順に確認した
- Loop / Fail Branch の DSL 構造の根拠: `vendor/dify/api/tests/fixtures/workflow/increment_loop_with_break_condition_workflow.yml`、`GET /apps/<id>/workflows/default-workflow-block-configs`(iteration の既定は `is_parallel: false`、`parallel_nums: 10`、`error_handle_mode: terminated`、`flatten_output: true`)、api コンテナ内の graphon 0.7.0(`nodes/loop/entities.py`、`entities/base_node_data.py`、`enums.py`、`graph_engine/error_handler.py`)。確認した事実は `research/dify-for-code-first-engineers/workflow-nodes.md` に追記した
- `iteration-batch.yml`(workflow 章、app_id `9a7b20fe-40c2-43b8-90a1-d2ccb3a59f0f`)は読み解きのみで再実行していない

## サンプル 1: loop-refine.yml

- アプリ名: `workflow-control-flow: loop-refine`、app_id: `595e1325-c965-4be6-8eee-d2adc284025f`
- 構成: start → loop(loop_start → writer(LLM)→ judge(LLM、構造化出力 `score` / `feedback`)→ parse(Code)→ assign(Variable Assigner))→ end。ループ変数 `draft` / `feedback` / `score` / `attempt`、終了条件 `score ≥ 8`、`loop_count: 3`
- 下書き保存: `POST /apps/<id>/workflows/draft` 成功(ノード 8)
- 下書き実行(`POST /apps/<id>/workflows/draft/run`、scratchpad の `run_draft2.py` で SSE を要約)

| 入力 | 周回ごとの score | 結果 |
| --- | --- | --- |
| 先週の出張で立て替えたタクシー代はどうやって精算すればいいですか。領収書はあります。 | 7 → 7 → 8 | `succeeded`、41.6 秒、`total_steps: 3`、outputs `{answer, score: 8, attempts: 3}`。`loop_completed` の outputs にループ変数と `loop_round: 3` |
| 来月の有給休暇を 3 日まとめて取りたいのですが、申請の締め切りはいつですか。 | 9 | `succeeded`、19.7 秒、1 周で終了条件を満たして終了。`attempts: 1` |

- 公開: `POST /apps/<id>/workflows/publish`(`marked_name: v1`)成功
- エクスポート: `GET /apps/<id>/export?include_secret=false` → `examples/dify-for-code-first-engineers/dsl/loop-refine.yml`(`version: 0.7.0`、ノード 8、依存 `langgenius/ollama:1.0.2@ef203a…`)。Loop ノードの `data` に `loop_count` / `break_conditions` / `logical_operator` / `loop_variables` / `start_node_id` が書き出されていることを確認
- 再インポート: `POST /apps/imports`(`yaml-content`、名前 `workflow-control-flow: loop-refine-reimport`、app_id `164b985e-f04d-4765-a4f2-e4d5d8f77551`)→ `status: completed`、`GET /apps/imports/<app_id>/check-dependencies` → `leaked_dependencies: []`
- Service API: `python/run_workflow.py --var question "ノート PC の電源が入らなくなりました。昨日までは使えていました。"`(API キーは `POST /apps/<id>/api-keys` で発行、scratchpad の `loop_apikey.json`)→ `succeeded`、113.2 秒、`steps: 3`、`score: 7`、`attempts: 3`(3 周しても 8 点に届かず `loop_count` で終了。本文の `:::message` に反映)
- 結果: 成功。judge の `score` は qwen2.5:7b でも整数で返ったが、parse(Code)で文字列を吸収する設計は残した

## サンプル 2: error-handling.yml

- アプリ名: `workflow-control-flow: error-handling`、app_id: `40403ae8-786f-49e0-b126-547cb2bdbe65`
- 構成: support-triage の 9 ノードに、User Input の `simulate_error`(select、`none` / `code`)、normalize(Code)の `error_strategy: fail-branch` と `retry_config: {retry_enabled: true, max_retries: 2, retry_interval: 500}`、例外分岐先の fallback(Template)と end_fallback(Output)を追加。計 11 ノード
- 下書き実行

| 入力 | 結果 |
| --- | --- |
| 社内 Wi-Fi に接続できなくなりました。(`simulate_error: none`) | `succeeded`、15.1 秒、6 ステップ。normalize → end の通常経路。category=IT、needs_human=false |
| 同上(`simulate_error: code`) | `node_retry` イベント 2 回(各 0.54 秒)→ normalize が `status: exception`、outputs に `error_type: CodeExecutionError` と `error_message`(サンドボックスのトレースバック `ValueError: simulated failure in normalize`)→ fallback → end_fallback。ワークフローは `partial-succeeded`、24.8 秒、`total_steps: 9` |

- 公開: `marked_name: v1` 成功
- エクスポート → `examples/dify-for-code-first-engineers/dsl/error-handling.yml`(`version: 0.7.0`、ノード 11)。エッジは `normalize --source--> end` と `normalize --fail-branch--> fallback`。`default_value` は書き出されない(Fail Branch のため)
- 再インポート: 名前 `workflow-control-flow: error-handling-reimport`、app_id `cc0725cf-7393-4add-be8a-0180f2385565` → `completed`、`leaked_dependencies: []`
- Service API(API キーは scratchpad の `err_apikey.json`)
  - `run_workflow.py "出張の日当は申請できますか。"` → `succeeded`、32.9 秒、6 ステップ、category=経費。ただし `answer` が中国語で返った(workflow 章と同じモデル側の揺れ。ワークフローとしては成功)
  - `simulate_error: code` を渡す実行は `run_workflow.py` が 1 変数しか受けないため、scratchpad から httpx で直接 `POST /v1/workflows/run` を呼んだ → HTTP 200、`data.status: partial-succeeded`、31.9 秒、`total_steps: 9`、outputs に `category` / `answer`(人手対応の文面)/ `error_type: CodeExecutionError` / `error_message`
- 結果: 成功。Fail Branch の `sourceHandle` 値は実機のエクスポートで確認済み(本文に記載)。キャンバス上の表示は著者確認待ち

## 本文に残した目印(`books/dify-for-code-first-engineers/workflow-control-flow.md`)

| 行 | 種別 | 内容 |
| --- | --- | --- |
| 12 | VERIFY | Iteration の設定パネルの 4 項目の表記と順序 |
| 13 | SCREENSHOT | iteration-batch の Iteration ノード設定パネル |
| 37 | TODO(要確認) | Iteration の最大並列数が web 側の `MAX_PARALLEL_LIMIT` だけで決まるか |
| 42 | VERIFY | Loop の設定パネルの 3 項目の表記と Exit Loop ノードの日本語 UI 名 |
| 125 | SCREENSHOT | error-handling の normalize ノードに Fail Branch のハンドルが付いたキャンバス |
| 136 | TODO(要確認) | `WORKFLOW_CALL_MAX_DEPTH` 超過時のエラーが親のどのノードに出るか |
| 137 | TODO(要確認) | `WORKFLOW_MAX_EXECUTION_STEPS` が Loop / Iteration 内のノードとリトライをどう数えるか(観測値: Loop の例で `total_steps: 3`、リトライ 2 回を含む例で 9) |
| 142 | VERIFY | ノード単体実行の入口と Last Run タブの位置 |
| 145 | VERIFY | Variable Inspect パネルのラベルと Reset all の位置 |
| 146 | SCREENSHOT | loop-refine を Test Run した後の Variable Inspect パネル |

(行番号は 2026-10-03 時点)

## 分量

- 本文文字数: 4,998 字(コードブロック・コメント・空白を除く、`count_chars.py`)。初稿は 5,877 字だったため、仕様の 3,500〜5,000 字に収まるまで削った

## 他章への申し送り

- service-api 章: `POST /v1/workflows/run` の `data.status` には `succeeded` / `failed` のほかに `partial-succeeded` がある。`python/run_workflow.py` は `succeeded` 以外を失敗扱いにしているので、service-api 章で判定を見直すか、`partial-succeeded` の扱いを本文で説明する
- limits-migration 章: `total_steps` の数え方(Loop 内のノードは含まれず、リトライは含まれるように見える)は未確認のまま TODO にした。`WORKFLOW_MAX_EXECUTION_STEPS` の超過実験をする際に合わせて確認する
- chatflow 章: Human Input と `interrupt` の対応はこの章の「まとめ」で chatflow 章へ振った
