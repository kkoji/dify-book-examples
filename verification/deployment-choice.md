# 検証記録: deployment-choice

- 日付: 2026-10-03
- 対象: Dify 1.17.1(セルフホスト、Docker Compose)。Ollama のモデルは使用していない
- 根拠にした調査メモ: `research/dify-for-code-first-engineers/deployment.md`、`limits-migration.md`、`VERSION.md`

## サンプル

- なし(この章は提供形態・ライセンス・判断軸の解説のみ。アプリの作成、API 呼び出しは行っていない)

## 本文の文字数

- 4,492 字(コードブロック・frontmatter・HTML コメント・空白を除く。`count_chars.py` で計測)。目安 3,500〜4,500 字の範囲内

## 本文に残した目印

| 行 | 種別 | 内容 |
| --- | --- | --- |
| 17 | TODO(要確認) | Premium と Community Edition の機能差がブランド変更以外にあるか(AWS Marketplace の商品ページ未確認) |
| 77 | VERIFY | `dataset_operator` ロールがメンバー管理画面でどの名前で表示され、何ができるか(著者が実機で確認) |
| 86 | TODO(要確認) | Dify Cloud のデータリージョン。現行 docs と pricing ページに記述がなく、日本リージョンの有無も未確認 |
| 103 | AUTHOR | 実運用での所感(著者記入欄) |

SCREENSHOT は残していない(章仕様どおり)。

## 章固有の確認事項

- 料金の数値(ドル額、クレジット数、文書数などプラン別の上限値)は本文に書いていない。「料金と上限は公式ページで確認する」の節に https://dify.ai/pricing と https://dify.ai/pricing/dify-enterprise へのリンクと、プランで変わる項目の種類だけを列挙した
- ライセンスの記述は deployment.md の LICENSE 1 項・1a・1b の行だけを根拠にしている(商用利用可、マルチテナント禁止 = 1 テナント 1 ワークスペース、フロントエンドのロゴ・著作権表示の改変禁止、フロントエンド不使用時は不適用)
