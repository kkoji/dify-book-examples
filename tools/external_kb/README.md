# external_kb: 外部ナレッジ API の最小実装

Dify の External Knowledge API 契約(`POST {endpoint}/retrieval`)を満たす FastAPI サーバーです。`data/policies/*.md` を `##` 見出し単位に分け、BM25(文字 2-gram)で検索して `records[]` を返します。自前の RAG を Dify のナレッジとして見せる最小構成の例で、本番ではこの検索部分を自分の検索基盤に差し替えます。

## 起動

```bash
cd examples/dify-for-code-first-engineers/tools/external_kb
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # EXTERNAL_KB_API_KEY を決める
set -a; . ./.env; set +a
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8101
```

動作確認:

```bash
curl -s http://localhost:8101/retrieval \
  -H "Authorization: Bearer $EXTERNAL_KB_API_KEY" -H 'Content-Type: application/json' \
  -d '{"knowledge_id":"policies","query":"タクシー代の精算","retrieval_setting":{"top_k":2,"score_threshold":0.0}}'
```

## Dify からの到達性(Docker Compose)

Dify の api / worker コンテナからホストのサービスを呼ぶときは、エンドポイントを `http://host.docker.internal:8101` にします。外部ナレッジへの通信は SSRF プロキシ(Squid)を経由するので、`docker/.env` に `SSRF_PROXY_ALLOW_PRIVATE_IPS` / `SSRF_PROXY_ALLOW_PRIVATE_DOMAINS` を設定して `host.docker.internal` を許可する必要があります(`ops/env.local.example` を参照)。

## Dify 側の登録

1. Knowledge 画面右上の External Knowledge API から、Name / API Endpoint(`http://host.docker.internal:8101`)/ API Key(`EXTERNAL_KB_API_KEY` の値)を登録する
2. Knowledge > Create > Connect to an External Knowledge Base で、上の API と External Knowledge ID(任意の文字列。`knowledge_id` としてそのまま届く)を指定してナレッジを作る

Console API で同じことをする場合は `POST /console/api/datasets/external-knowledge-api` と `POST /console/api/datasets/external` を使います(検証記録 `verification/knowledge.md` を参照)。
