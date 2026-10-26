# 検証記録: dsl-versioning 章

- 日付: 2026-10-03
- Dify: 1.17.1(セルフホスト、Docker Compose。`vendor/dify` はタグ 1.17.1)
- LLM: この章の検証ではモデルを呼ばない(DSL に `langgenius/ollama/ollama` の `qwen2.5:7b` を参照するノードが入っているだけ)
- 本文の文字数: 5997(`count_chars.py`、コードブロック・コメント・空白を除く)
- 前任エージェントの成果物(scratchpad の `dslv/`、アプリ `dsl-versioning: secret-env` 2 つ)を引き継ぎ、本記録のコマンドはすべて今回あらためて実行した
- Console API は scratchpad の `console.sh`(Cookie + CSRF)で叩いた。ログインは済んでいたので再ログインしていない

## 作成・使用したアプリ

| アプリ名 | app_id | 用途 |
| --- | --- | --- |
| `dsl-versioning: secret-env` | `03bed196-7e0c-46d7-b984-0bbd5a43fb45` | 本体。secret 型環境変数 `API_KEY`(値 `sk-dummy-1234`)と string 型 `STAGE` を持つ 3 ノードの Workflow。公開版 v1(`83d3dda4-…`、version_number 1)と v2(`74038701-…`、version_number 2、「LLM ノードを下に移動しただけ」) |
| `dsl-versioning: secret-env-reimport` | `b8332834-8418-4dc9-8481-faa53d68e299` | 前任が `include_secret=false` の DSL を再インポートしたもの(`include_secret=true` でエクスポートしても `API_KEY` は空)。今回名前に `-reimport` を付けた |
| `dsl-versioning: secret-env-imported-with-secret` | `fc54d4a8-9874-40ce-a27a-315ac8f3d306` | `include_secret=true` の DSL(平文 `sk-dummy-1234` 入り)を新規インポート |
| `dsl-versioning: version-pending` | `64890408-cf53-454b-84ce-b8bd34c088d9` | `version: 0.8.0` に書き換えた DSL を `promote.sh` + `FORCE=1` で取り込み |
| `dsl-versioning: version-warn` | `7bfdac6c-66ab-460f-863b-a2d8c199c2d5` | `version: 0.6.0` に書き換えた DSL を取り込み |
| `workflow: support-triage-reimport` | `090a48e8-4b17-4a29-b11b-e55bbd148120` | workflow 章のアプリ。`promote.sh` の `app_id` 上書きインポートの対象に使った(前任が名前を「overwrite into support-triage-reimport (workflow)」に変えていたので、元の名前に戻した。下書きは `support-triage-workflow.yml` と同内容) |

## サンプル 1: `ops/dsl_export_all.sh`

- コマンド: `DIFY_CONSOLE_URL=http://localhost/console/api DIFY_EMAIL=… DIFY_PASSWORD=… ./dsl_export_all.sh <scratchpad>/dslv2/out`(`COMMIT` なし)
- 結果: 成功。ワークスペースの 12 アプリ(workflow 9、chat 3。他章の検証アプリを含む)が `<app_id 先頭 8 桁>-<名前>.yml` で出力された
- `COMMIT=1` の経路(`git add` → `git diff --cached --quiet` → `git commit`)は本リポジトリを汚さないため未実行。構文は `bash -n` で確認
- 末尾の `difyctl` 版はコメントのみ(下記「difyctl」参照)。`<!-- VERIFY -->` を残した

## サンプル 2: `ops/promote.sh`

| 実行 | コマンド | 結果 |
| --- | --- | --- |
| 既存 Workflow への上書き | `./promote.sh dsl/support-triage-workflow.yml 090a48e8-…` | `status: completed`、`app_id` は上書き先のまま、`leaked_dependencies: []`。上書き後も `GET /apps/090a48e8-…/workflows` の `items` は空(公開版は作られず下書きだけが入れ替わる) |
| `version: 0.8.0` を FORCE なし | `./promote.sh dslv2/v080.yml` | `status: pending`、`app_id: null`、`imported_dsl_version: 0.8.0`、`current_dsl_version: 0.7.0`。スクリプトは exit 2 で止まり「FORCE=1 で再実行」を案内 |
| `version: 0.8.0` を `FORCE=1` | `FORCE=1 ./promote.sh dslv2/v080.yml` | `pending` → `POST /apps/imports/<id>/confirm` → `status: completed`、app_id `64890408-…` |
| `version: 0.6.0` | `./promote.sh dslv2/v060.yml` | `status: completed-with-warnings`、`warnings: []`、app_id `7bfdac6c-…` |

- 結果: 成功。「次にやること」の Console 手作業(認証情報の設定、Publish)は著者確認待ち

## サンプル 3: `ops/dsl_diff_filter.py` と `ops/gitattributes.example`

- scratchpad に空の git リポジトリを作り、`.gitattributes` に `dsl/*.yml diff=dify-dsl`、`git config diff.dify-dsl.textconv "python3 ops/dsl_diff_filter.py"` を設定
- LLM ノードの `position.y` / `positionAbsolute.y` だけが違う 2 つのエクスポート(227 と 300)を commit 前後に置いて `git diff` → 出力なし。`git diff --no-textconv` → 4 行(`y: 227` → `y: 300` が 2 か所)。`git diff --stat` は textconv が効かず `2 insertions(+), 2 deletions(-)` と出る
- さらにプロンプトの「3 文以内」を「2 文以内」に変えて `git diff` → `prompt_template` の `text` 行の 1 行差分だけが表示された
- 結果: 成功。PyYAML は `python/requirements.txt` の 6.0.2 を使った

## 差分ノイズの実測(研究メモの未確認欄を解消)

対象: `dsl-versioning: secret-env`(`03bed196-…`)。コマンドは scratchpad の `dslv2/diff_test.sh`。

| 手順 | 結果 |
| --- | --- |
| 同じ下書きを続けて 2 回 `GET /apps/<id>/export?include_secret=false` | SHA-256 が一致(`7ad26b42…`)。バイト単位で同一 |
| LLM ノードの `position.y` / `positionAbsolute.y` を 300 → 227 に変えて `POST /workflows/draft`(`hash` 付き)→ 再エクスポート | 差分は `y:` の 2 行だけ。ノード ID、キー順、他ノード、`edges` は不変 |
| `include_secret=true` と `false` の diff | `API_KEY` の `value: ''` ↔ `value: sk-dummy-1234` の 1 行だけ |
| `export?workflow_id=<v1 の id>` と下書きの diff | 下書きの座標を v1 と同じに戻した状態では同一(座標が違うときは `y:` の 2 行だけ) |
| `export?workflow_id=<下書きの id>` | HTTP 500(`Internal Server Error`)。公開版の id だけ指定できる |

注: 前任が下書きを y=300 の状態で残していたため、今回は 300 → 227 の方向で動かした。現在の下書きは y=227(v1 と同じ)で、v2 だけが y=300。

## include_secret=true の DSL の取り込み

- `include_secret=true` でエクスポートした YAML(`sk-dummy-1234` 平文入り)を `POST /apps/imports`(`yaml-content`)で新規インポート → `completed`、app_id `fc54d4a8-…`
- 新アプリを `include_secret=true` でエクスポート → `value: sk-dummy-1234`。`include_secret=false` → `value: ''`
- 結論: 同一ワークスペース内では平文 secret は保存され、再エクスポートで同じ値が返る。別ワークスペースへの取り込みは、本環境でワークスペースを増やせない(`ALLOW_CREATE_WORKSPACE=false`)ため未検証

## difyctl

- 導入: 公式ドキュメント(`/en/cli/install`)の手順は、インストールスクリプト `install-cli.sh`、または GitHub Releases の `difyctl-v<version>-<os>-<arch>` + checksums。前任が Releases から取得した `difyctl-v1.17.1-darwin-arm64`(scratchpad `dslv/difyctl`)の SHA-256 `9c550176…` が `difyctl-v1.17.1-checksums.txt` の値と一致することを確認。brew / pip の配布は無い(`brew info difyctl` は formula なし。PyPI の `dify-cli` は別物)
- `difyctl version` → `Version: 1.17.1 (channel: stable)`、`Commit: 8387590`、`Compat: dify >=1.16.0, <=1.17.1`
- 認証: `difyctl auth login --host http://localhost` → `usage_invalid_flag: only https:// hosts are accepted`(`--insecure` が要る)。`--insecure --no-browser` を付けると `unsupported_endpoint: this Dify host does not implement the OAuth device flow`(HTTP 404)。公式クイックスタートどおり、サーバ側で `OPENAPI_ENABLED=true` と `ENABLE_OAUTH_BEARER=true`(`envs/core-services/shared.env.example`、既定 `false`)が必要。共有の `vendor/dify/docker/.env` を変えない方針なので、**CLI の export / import は未検証(著者確認待ち)**。ブラウザ無しの代替はヘルプにある `DIFY_TOKEN`(bearer)のみで、これも bearer 有効化が前提
- 以上を `research/dify-for-code-first-engineers/dsl-versioning.md` の末尾「追記」に反映した

## 代替した検証と未検証

- 別ワークスペースへの移行 → 同一ワークスペース内の別アプリへの `app_id` 上書き(上記サンプル 2)で代替
- `DSL_EXPORT_ENCRYPT_DATASET_ID=false` → `.env` 変更が要るため未実施。ワークスペースに Knowledge Retrieval ノードを持つアプリもまだ無い(knowledge 章が未着手)。本文に VERIFY
- GUI(Export DSL ダイアログ、バージョン履歴パネル)→ 著者確認待ち
- deployment v2(「Push versions to environments」)の Community での可用性 → 未確認、本文に TODO

## 本文に残した目印(`books/dify-for-code-first-engineers/dsl-versioning.md`)

| 行 | 種別 | 内容 |
| --- | --- | --- |
| 39 | SCREENSHOT | Export DSL のシークレット確認ダイアログ |
| 95 | VERIFY | バージョン履歴パネルを開く操作と右クリックメニューの表記 |
| 96 | SCREENSHOT | バージョン履歴パネル |
| 110 | VERIFY | `OPENAPI_ENABLED` / `ENABLE_OAUTH_BEARER` を有効にして difyctl の login → export → import --app-id |
| 122 | VERIFY | `DSL_EXPORT_ENCRYPT_DATASET_ID=false` で `dataset_ids` が平文になり別ワークスペースで参照が保たれること |
| 126 | TODO(要確認) | deployment v2 が Community Edition で使えるか |

## 分量

- 本文文字数: 5997 字(初稿 9,121 字から仕様の節構成を保ったまま削った)
- `python3 <scratchpad>/count_chars.py books/dify-for-code-first-engineers/dsl-versioning.md`

## 他章への申し送り

- workflow 章: `workflow: support-triage-reimport`(`090a48e8-…`)の下書きを、この章の上書きインポート検証で `support-triage-workflow.yml` の内容に置き換えた(内容は同じ DSL なので実害は無いはず)。名前は元に戻した
- setup / production-config 章: `difyctl` を使うなら `OPENAPI_ENABLED` と `ENABLE_OAUTH_BEARER`(`shared.env`)を有効にする手順が要る。本章では VERIFY 止まり
- knowledge 章: Knowledge Retrieval ノードを持つアプリができたら、`DSL_EXPORT_ENCRYPT_DATASET_ID` の確認に使える(本章の VERIFY)
- 執筆ガイドの手順 2 の補足: `POST /workflows/draft` は `GET /workflows/draft` の `hash` をそのまま渡せば楽観ロックを通る。1 回の保存で `hash` が変わるので、連続保存では毎回取り直す
