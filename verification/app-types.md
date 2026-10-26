# 検証記録: app-types

- 日付: 2026-10-03
- 環境: Dify 1.17.1(セルフホスト、Docker Compose、http://localhost)、Ollama `qwen2.5:7b`(プラグイン `langgenius/ollama` 1.0.2)
- Python: `examples/dify-for-code-first-engineers/python/.venv`(httpx 0.28.1、python-dotenv 1.1.1)

## サンプル 1: `dsl/chatbot-minimal.yml`(Chatbot、`mode: chat`)

- 作成したアプリ: `app-types: chatbot-minimal`(app_id `e9d27596-d5ad-4b05-ae36-367beb250b56`)
- 再インポートで作られたアプリ: `app-types: chatbot-minimal-reimport`(app_id `517f4550-d7ca-48d8-8130-92c149645643`)
- 手順と結果

| 手順 | コマンド(Console API は `console.sh` 経由) | 結果 |
| --- | --- | --- |
| アプリ作成 | `POST /apps {"name":"app-types: chatbot-minimal","mode":"chat",...}` | 成功 |
| モデル設定 | `POST /apps/<id>/model-config`(provider `langgenius/ollama/ollama`、name `qwen2.5:7b`、`prompt_type: simple`、`pre_prompt` 設定) | 成功 `{"result":"success"}` |
| エクスポート | `GET /apps/<id>/export?include_secret=false` の `data` を `dsl/chatbot-minimal.yml` に保存 | 成功。`version: 0.7.0`、`dependencies` に `langgenius/ollama:1.0.2@ef20...`。秘密情報なし |
| 再インポート | `POST /apps/imports {"mode":"yaml-content","yaml_content":<YAML>,"name":"app-types: chatbot-minimal-reimport"}` | `status: completed`、`app_mode: chat`、`imported_dsl_version: 0.7.0`、warnings なし |
| 依存チェック | `GET /apps/imports/517f4550-.../check-dependencies` | `leaked_dependencies: []` |
| API キー発行 | `POST /apps/<id>/api-keys` | 成功(キーは scratchpad に保管、リポジトリには置かない) |
| Service API | `DIFY_APP_API_KEY=app-... .venv/bin/python app_types_check.py` | 成功。`GET /v1/info` → `mode=chat`。`POST /v1/chat-messages`(blocking)→ `conversation_id=a20483eb-4541-4778-901d-44aec29dc9ab`、回答あり |

## サンプル 2: `dsl/workflow-minimal.yml`(Workflow、`mode: workflow`、User Input → LLM → Output)

- 作成したアプリ: `app-types: workflow-minimal`(app_id `4945c5b9-cab9-4a21-bc24-49c513d38a54`)、公開バージョン名 `v1`
- 再インポートで作られたアプリ: `app-types: workflow-minimal-reimport`(app_id `e3e790e5-3d5f-4fab-a98b-62531904dee3`)
- 手順と結果

| 手順 | コマンド | 結果 |
| --- | --- | --- |
| アプリ作成 | `POST /apps {"name":"app-types: workflow-minimal","mode":"workflow",...}` | 成功 |
| 下書き保存 | `POST /apps/<id>/workflows/draft {"graph":{...},"features":{...},"conversation_variables":[],"hash":null}` | 成功。`hash` が返る |
| 下書き実行 | `POST /apps/<id>/workflows/draft/run {"inputs":{"question":"有給休暇の申請はいつまでに出せばよいですか?"},"response_mode":"blocking"}` | `workflow_finished` で `status: succeeded`、`outputs.answer` あり、`total_steps: 3`、`total_tokens: 81` |
| 公開 | `POST /apps/<id>/workflows/publish {"marked_name":"v1","marked_comment":"app-types 章の最小 Workflow"}` | 成功 |
| エクスポート | `GET /apps/<id>/export?include_secret=false` → `dsl/workflow-minimal.yml` | 成功。`version: 0.7.0`、3 ノード 2 エッジ、秘密情報なし |
| 再インポート | `POST /apps/imports`(`name: app-types: workflow-minimal-reimport`) | `status: completed`、`app_mode: workflow`、`imported_dsl_version: 0.7.0`、warnings なし |
| 依存チェック | `GET /apps/imports/e3e790e5-.../check-dependencies` | `leaked_dependencies: []` |
| API キー発行 | `POST /apps/<id>/api-keys` | 成功(scratchpad に保管) |
| Service API | `DIFY_APP_API_KEY=app-... .venv/bin/python app_types_check.py` | 成功。`GET /v1/info` → `mode=workflow`。`POST /v1/workflows/run`(blocking)→ `workflow_run_id=1b1a8483-af74-4338-a8ea-861f17790d82`、`status=succeeded`、`outputs.answer` あり |

## 作業中に分かったこと(writing-guide.md との差分)

- `POST /apps/<id>/workflows/draft` のボディに `environment_variables: []` を入れると 400(`SyncDraftWorkflowPayload` が `extra_forbid`)。1.17.1 では `environment_variable_patch` を使う。環境変数がなければキーごと省略する
- LLM ノードの `memory` を `{"enabled": false}` だけで書くと実行時に `memory.window Field required` で失敗する。メモリを使わないなら `memory` キーごと省略する(エクスポートにも出ない)
- `python/.env.example` は既存(`DIFY_APP_API_KEY` / `DIFY_KNOWLEDGE_API_KEY`)。この章のスクリプトもそれに合わせた

## 著者確認待ち

- GUI でのインポート操作(「Import DSL file」→「From DSL file」)は著者が実機で行う。Console API 経由の再インポートは上記のとおり成功

## 本文に残した目印(`books/dify-for-code-first-engineers/app-types.md`)

| 行 | 種類 | 内容 |
| --- | --- | --- |
| 11 | SCREENSHOT | アプリ作成モーダル(Workflow / Chatflow と「More basic app types」を開いた状態) |
| 12 | SCREENSHOT | Agents ページ |
| 29 | VERIFY | 新 Agent(mode: agent)が Studio のアプリ一覧に表示されるか |
| 58 | VERIFY | 「Switch to Workflow Orchestrate」がアプリ画面のどのメニューにあるか |
| 72 | AUTHOR-REVIEW | コードの概念との対応の節 |
| 216 | AUTHOR | 実運用での所感 |

TODO(要確認) は残していない。

## 本文の文字数

- 4996 字(`count_chars.py`、コードブロック・コメント・空白を除く)。章仕様の目安 3,500〜5,000 字
