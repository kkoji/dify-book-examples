# hybrid: Dify と LangGraph を双方向につなぐ

limits-migration 章の題材。Dify を残したまま一部をコードへ逃がす 2 つの向きを、それぞれ最小の形で置いている。

| 向き | ファイル | 役割 |
| --- | --- | --- |
| Dify → コード | `service.py` | workflow 章の分類(Question Classifier)を LangGraph のサブグラフに置き換えた FastAPI サービス。Dify の HTTP Request ノードから `POST /classify` で呼ぶ。Dify 側の DSL は `../../dsl/hybrid-workflow.yml` |
| コード → Dify | `langgraph_calls_dify.py` | LangGraph のグラフの 1 ノードから Dify の Workflow(`POST /v1/workflows/run`)を呼び、`needs_human` で LangGraph 側の条件付きエッジが分岐する |

## 準備

```bash
cd examples/dify-for-code-first-engineers/python/hybrid
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # DIFY_APP_API_KEY に workflow 章の support-triage の app- キーを書く
```

`python/.venv`(共通)とは別の venv を作る。LangGraph の入門は本書の範囲外なので、API の詳細は LangGraph の公式ドキュメントを参照する。

## Dify → コード(service.py)

```bash
.venv/bin/uvicorn service:app --host 0.0.0.0 --port 8104
curl -s -X POST http://localhost:8104/classify -H 'Content-Type: application/json' \
  -d '{"question": "タクシー代はどうやって精算すればいいですか"}'
# {"category":"経費","raw":"経費"}
```

Docker Compose の Dify から到達させるので、HTTP Request ノードの URL は `http://host.docker.internal:8104/classify`。`host.docker.internal` はプライベートアドレスなので、`ops/env.local.example` の `SSRF_PROXY_ALLOW_PRIVATE_IPS` / `SSRF_PROXY_ALLOW_PRIVATE_DOMAINS` を `docker/.env` に足しておく(tools-mcp 章と同じ)。

`dsl/hybrid-workflow.yml` を Studio の「Import DSL file」で取り込み、公開してから実行する。構成は User Input → HTTP Request(classify)→ Code(JSON から `category` を取り出す)→ LLM(種別に合わせて回答案)→ Output。

## コード → Dify(langgraph_calls_dify.py)

```bash
.venv/bin/python langgraph_calls_dify.py "先週の出張で立て替えたタクシー代はどうやって精算すればいいですか。"
```

`call_dify` ノードが blocking で Workflow を呼び、`data.status` が `failed` なら例外、`partial-succeeded` は結果として扱う。`needs_human` が真なら `escalate`、偽なら `auto_reply` に進む。

## 検証

- 2026-10-05、Dify 1.17.1(セルフホスト)、Ollama `qwen3:8b`、langgraph 1.2.12 / langchain-ollama 1.1.0 / fastapi 0.142.2、Python 3.12.10
- 詳細は `examples/dify-for-code-first-engineers/verification/limits-migration.md`
