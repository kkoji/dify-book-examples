# internal_api: 社内 API のダミー(FastAPI)

tools-mcp 章で Dify のカスタムツールに登録する題材。社員情報照会(`GET /employees/{employee_id}`)と IT 機器申請(`POST /it-requests`)の 2 エンドポイントを持ち、ヘッダー `X-API-Key` で認証する。

## 起動

```bash
cd examples/dify-for-code-first-engineers/tools/internal_api
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # INTERNAL_API_KEY を書き換える
INTERNAL_API_KEY=$(grep INTERNAL_API_KEY .env | cut -d= -f2) .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8102
```

## OpenAPI 仕様の書き出し

Dify の取り込みには `servers` が必須。Docker Compose の Dify からホスト側へ到達させるので `http://host.docker.internal:8102` を渡す。

```bash
.venv/bin/python export_openapi.py http://host.docker.internal:8102 > openapi.json
```

## Dify 側の準備(Docker Compose)

`host.docker.internal` はプライベートアドレスなので、SSRF プロキシの許可設定が要る。`ops/env.local.example` の `SSRF_PROXY_ALLOW_PRIVATE_IPS` / `SSRF_PROXY_ALLOW_PRIVATE_DOMAINS` を `docker/.env` に追記して `docker compose up -d` し直す。

## 検証

- 2026-10-03、Dify 1.17.1、fastapi 0.142.2 / uvicorn 0.54.0、Python 3.12.10
- Console API `POST /console/api/workspaces/current/tool-provider/api/add` で登録し、`get_employee` と `create_it_request` の 2 ツールが作られた。詳細は `examples/dify-for-code-first-engineers/verification/tools-mcp.md`
