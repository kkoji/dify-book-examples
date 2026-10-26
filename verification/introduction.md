# 検証記録: introduction

- 日付: 2026-10-03
- 対象: Dify 1.17.1(セルフホスト、Docker Compose)。Ollama `qwen2.5:7b` / `nomic-embed-text`
- 章ファイル: `books/dify-for-code-first-engineers/introduction.md`

## サンプル

- なし(この章は図のみ。DSL・Python サンプルは作成していない)。検証対象なし

## 本文の文字数

- 4498 字(コードブロック・HTML コメント・frontmatter・空白を除く。`count_chars.py` で計測)。章仕様の目安 3,500〜4,500 字に収まる

## 本文に残した目印

| 行 | 種別 | 内容 |
| --- | --- | --- |
| 27 | TODO(要確認) | 実行時にノードやエッジを追加する手段(動的グラフ)が公式に無いことの一次情報。limits-migration.md に該当する事実表の行がない |
| 31 | AUTHOR-REVIEW | LangChain / LangGraph との対応づけ(chain = Chatbot / Text Generator、graph = Workflow / Chatflow、agent loop = Legacy Agent / Agent ノード / 新 Agent、state = 変数、checkpoint = Human Input)は著者が確認する |
| 37 | SCREENSHOT | 構成要素の関係図を作図。アプリ(5 種 + 新 Agent)、ノード、ナレッジ、ツール(4 種)、プラグイン(6 種)、トリガー、公開形態(Web アプリ / API / 埋め込み / MCP サーバー)の関係。画像は `/images/dify-for-code-first-engineers/` に置く |
| 83 | AUTHOR | 実運用での所感(著者記入欄) |

VERIFY: なし(GUI 手順を書いていない)

## 根拠にした調査メモ

- app-types.md(アプリ種別 5 つと mode、新 Agent、公開形態 4 つ、DSL の最上位キー)
- agent.md(3 つのエージェントの呼び分け、ループで制御できる範囲、新 Agent のサンドボックスと Skill)
- dsl-versioning.md(DSL 0.7.0、「エンジニアリング標準」の位置づけ)
- limits-migration.md(graphon 0.7.0、LangChain 非依存、Human Input、Service API の再開エンドポイント、公式ブログ「Dify vs LangChain」、プラグイン 6 種)
- deployment.md(提供形態 4 つ、ライセンスの追加条件)
- workflow-nodes.md(組み込みノード 25 種弱、変数記法、Trigger 3 種)、tools-mcp.md(ツール 4 種)
- VERSION.md(1.17.1、2026-09-10 公開)
