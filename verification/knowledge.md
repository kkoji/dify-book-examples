# 検証記録: knowledge 章

- 日付: 2026-10-03(初回)、2026-10-05(再確認)
- 環境: Dify 1.17.1(セルフホスト、Docker Compose、Weaviate 1.39.2)、Ollama `nomic-embed-text`(埋め込み)/ `qwen2.5:7b`(LLM、プラグイン `langgenius/ollama` 1.0.2)、Python 3.10 / httpx 0.28.1
- Knowledge API キー: Console API `POST /console/api/datasets/api-keys`(`dataset_ids: []`)で発行。接頭辞は `dataset-`(公式ドキュメントの `ds-` と異なる。本文 134 行目の VERIFY)。キーは scratchpad の `knowledge.env` に保管し、リポジトリには書かない。ナレッジ単位の `POST /console/api/datasets/<id>/api-keys` は 500 を返した(2026-10-03)
- 作成したナレッジ(消していない。著者が GUI で確認する材料)

| 名前 | dataset_id | 種別 | 内容 |
| --- | --- | --- | --- |
| `knowledge: policies` | `8c3841bf-defe-4c97-a78f-1ce64ccc4f33` | high_quality、General、`\n\n` / 500 / 50、Hybrid(Weighted 0.7 : 0.3)、Top K 3 | 規程 6 本、1 文書 6〜7 チャンク。rag-chatflow が参照 |
| `knowledge: policies-newline` | `5496c2bd-a680-4529-8f4f-d171a25503bb` | high_quality、General、既定の `\n` / 500 / 50 | 規程 6 本、1 文書 18〜20 チャンク(区切り文字の比較用) |
| `knowledge: policies-economy` | `db84f2f1-4e24-41a8-884d-5b1ac9e6f9aa` | economy(jieba) | 規程 3 本。`keyword_search` のスコアがすべて 0.0 |
| `knowledge: policies-external` | `a827e8e4-1450-4836-b73f-5d4738333783` | external(External Knowledge API `knowledge: external-kb`、`3ab50ceb-8ba8-4134-b5b6-57796f26bf38`、endpoint `http://host.docker.internal:8101`、External Knowledge ID `policies`) | tools/external_kb 経由 |
| `knowledge: policies-recheck` | `af92407b-5fe5-41f2-be44-fbd2d4eaf8e6` | high_quality、General、`\n\n` / 500 / 50 | 2026-10-05 に knowledge_ingest.py を再実行して作成 |

- 作成したアプリ: `knowledge: rag-chatflow`(app_id `37b24e41-5200-4bbc-99af-70be841310dc`、Chatflow、公開済み v1)、再インポート確認用 `knowledge: rag-chatflow-reimport`(`9c387fe2-b18d-4f0d-98bc-f7b999c01884`)。アプリ API キーは scratchpad の `rag_apikey.json`

## サンプル 1: python/knowledge_ingest.py(Knowledge API で一括投入)

- コマンド(`python/` で実行、環境変数は `.env` か export):

```bash
.venv/bin/python knowledge_ingest.py ../data/policies --name "knowledge: policies-recheck" --separator "\n\n"
```

- 結果(2026-10-05): 成功。`POST /datasets` → `POST /datasets/{id}/metadata`(department: string、effective_date: time)→ 6 文書を `create-by-file` → `indexing-status` をポーリング(表示された状態は `parsing` / `splitting` / `indexing` → `completed`、各文書数秒)→ `POST /datasets/{id}/documents/metadata` で値を付与。チャンク数は attendance 7、expense 7、it-equipment 7、onboarding 6、security 7、travel 7(2026-10-03 の `knowledge: policies` と同じ)
- 2026-10-03 の初回実行では `--separator "\n"`(既定の区切り)で `knowledge: policies-newline` を作り、18〜20 チャンク / 文書になることを確認(scratchpad `knowledge_ingest_run2.txt`)
- 注意: ナレッジ名はワークスペース内で一意。同名で再実行すると `POST /datasets` が失敗するので `--name` を変える

## サンプル 2: python/knowledge_retrieve.py(検索方式の比較)

- コマンド(`DIFY_DATASET_ID=8c3841bf-defe-4c97-a78f-1ce64ccc4f33`):

```bash
.venv/bin/python knowledge_retrieve.py "パスワードは何文字以上にする必要がありますか"
.venv/bin/python knowledge_retrieve.py "タクシー代は精算できますか" --method hybrid_search --department general-affairs
```

- 結果(2026-10-05): 成功。`semantic_search` 3 件(本命 security.md #3 は 2 位、0.6845)、`full_text_search` 0 件、`hybrid_search` 3 件(本命が 1 位、0.6206)。2026-10-03 の結果(scratchpad `knowledge_retrieve_run1.txt`、3 クエリ)と同じ順位で、本文 44〜55 行目の出力はこの結果
- `--department general-affairs` では travel.md と expense.md のチャンクだけが返り、`metadata_filtering_conditions` が `retrieve` でも効くことを確認
- `full_text_search` が日本語クエリで 0 件になる原因は未確認(本文 58 行目の TODO)

## サンプル 3: tools/external_kb(外部ナレッジ API)

- 起動: `tools/external_kb/.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8101`(`EXTERNAL_KB_API_KEY` は scratchpad `external_kb.env`。2026-10-05 時点でも起動したまま、ログは scratchpad `external_kb.log`)
- 直接呼び出し(2026-10-05): `curl -s http://localhost:8101/retrieval -H "Authorization: Bearer $EXTERNAL_KB_API_KEY" -d '{"knowledge_id":"policies","query":"タクシー代の精算","retrieval_setting":{"top_k":2,"score_threshold":0.0}}'` → 200、`records` 2 件(経費精算規程 / 交通費の扱い 1.0、出張規程 / 精算 0.4355)。誤ったキーは 403
- Dify からの到達(2026-10-05): `console.sh POST /datasets/a827e8e4-1450-4836-b73f-5d4738333783/external-hit-testing '{"query":"タクシー代は精算できますか","external_retrieval_model":{"top_k":2,"score_threshold":0.0,"score_threshold_enabled":false}}'` → 200、`records` 2 件(出張規程 / 精算 1.0、経費精算規程 / 交通費の扱い 0.6353)。外部サーバーのログに Dify のコンテナ(192.168.80.13)からの `POST /retrieval 200` が残った。SSRF プロキシの許可は `ops/env.local.example` の `SSRF_PROXY_ALLOW_PRIVATE_IPS` / `SSRF_PROXY_ALLOW_PRIVATE_DOMAINS` で設定済み
- Dify 側の登録(2026-10-03)は Console API `POST /console/api/datasets/external-knowledge-api`(scratchpad `external_api.json`)と `POST /console/api/datasets/external`(`external_dataset.json`)で行った。GUI の画面項目は著者確認待ち(本文 154 行目の VERIFY)
- 所見: Service API の `POST /v1/datasets/{id}/retrieve` を外部ナレッジに対して呼ぶと 200 で `records: []` が返り、外部サーバーには届かなかった。外部ナレッジを API で試すときは Console の `external-hit-testing` かアプリ経由を使う(調査メモに追記済み)
- 再検証(2026-10-06、通読レビュー RN-6): Python 3.12.10、`fastapi==0.142.2` / `uvicorn==0.54.0` で `.venv` を作り直した。直接呼び出しは 2026-10-05 と同じ 2 件・同じスコア(経費精算規程 / 交通費の扱い 1.0、出張規程 / 精算 0.4355)、誤ったキーは 403。`external-hit-testing` も同じ 2 件・同じスコア(出張規程 / 精算 1.0、経費精算規程 / 交通費の扱い 0.6353)で、サーバーに Dify のコンテナからの `POST /retrieval 200` が残った
- 結果: 成功(API 経由)。GUI での登録手順は著者確認待ち

## サンプル 4: dsl/rag-chatflow.yml(Knowledge Retrieval + メタデータフィルタ)

- 作り方(2026-10-03): scratchpad `build_rag_chatflow.py` でグラフを生成し、Console API で下書き保存 → 公開(`marked_name: v1`)→ `GET /apps/<id>/export?include_secret=false` → `dsl/rag-chatflow.yml`。`dataset_ids` は 64 文字の暗号化文字列。再インポート(`knowledge: rag-chatflow-reimport`)は `status: completed`、下書きには元の UUID が復元された
- ノード: start(Select 型 `department`: general-affairs / human-resources / information-systems)→ kr(Knowledge Retrieval、`sys.query`、Weighted 0.7 : 0.3、Top K 4、Manual 条件 `department is {{#start.department#}}`)→ llm(qwen2.5:7b、Context = `kr.result`)→ answer
- Service API(2026-10-05、`POST /v1/chat-messages`、`response_mode: blocking`、query「タクシー代は精算できますか」):

| inputs.department | answer | retriever_resources |
| --- | --- | --- |
| general-affairs | はい、終電後または重い荷物がある場合に限り認めており、利用理由を申請に記入する必要があります。 | 3 件(travel.md 0.5809、expense.md 0.4894、expense.md 0.4680)。`doc_metadata` は `{department: general-affairs, effective_date: 1775001600}` |
| human-resources | 規程に記載がありません。担当部署に確認してください。 | 3 件(attendance.md、onboarding.md ×2。すべて `department: human-resources`) |

- ノード側 Top K 4 に対して返るのは 3 件(ナレッジ側 Top K 3 が上限になる。2026-10-03 の観察と同じ)
- 結果: 成功。Knowledge Retrieval ノードの画面項目、N-to-1 の有無、Manual 条件で会話変数を選べるかは著者確認待ち

## 本文に残した目印(`books/dify-for-code-first-engineers/knowledge.md`)

| 行 | 種別 | 内容 |
| --- | --- | --- |
| 17 | VERIFY | ナレッジ作成画面での General / Parent-child の最大チャンク長とオーバーラップの既定表示値 |
| 18 | SCREENSHOT | ナレッジ作成のチャンク設定画面 |
| 30 | TODO(要確認) | 日本語での Economical の精度 |
| 58 | TODO(要確認) | 既定の Weaviate 構成で日本語の Full-Text Search が 0 件になる原因 |
| 63 | SCREENSHOT | ナレッジの Metadata パネルと文書一覧の一括編集 |
| 77 | VERIFY | GUI 手順 2〜3 の画面項目名(Retrieval Setting、Manual、Context) |
| 78 | VERIFY | Knowledge Retrieval ノードに N-to-1(single)モードの選択肢が残っているか |
| 79 | SCREENSHOT | Knowledge Retrieval ノードの設定パネル |
| 119 | VERIFY | Manual 条件の Variable に会話変数を選べるか |
| 126 | SCREENSHOT | Retrieval Testing 画面と Records |
| 127 | VERIFY | Retrieval Testing 画面の項目名と Records の表示内容 |
| 134 | VERIFY | Knowledge 画面の Service API で発行したキーの接頭辞(`ds-` か `dataset-` か) |
| 154 | VERIFY | External Knowledge API の登録画面と Connect to an External Knowledge Base の項目名 |

- 章仕様にある `ATTACHMENT_IMAGE_FILE_SIZE_LIMIT` 既定値の TODO は、本文で画像添付に触れなかったため置いていない
- Rerank モデルは検証環境に無く、Rerank 経由の挙動は未検証(本文 38 行目に明記)

## 本文の文字数

- 5,980 字(`count_chars.py`、コードブロック・コメント・空白を除く。目安 5,000〜6,000)
