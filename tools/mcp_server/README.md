# mcp_server: Streamable HTTP の最小 MCP サーバー

tools-mcp 章で Dify に「外部 MCP サーバー」として登録する題材。公式 `mcp` パッケージの `FastMCP` でツールを 2 つ(`get_office_hours`、`lookup_policy`)公開する。

## 起動

```bash
cd examples/dify-for-code-first-engineers/tools/mcp_server
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python server.py   # http://0.0.0.0:8103/mcp
```

Dify への登録時のサーバー URL は `http://host.docker.internal:8103/mcp`(パス末尾の `mcp` で Streamable HTTP と判定される)。SSRF プロキシの許可設定は `internal_api/README.md` と同じ。

## 検証

- 2026-10-03、Dify 1.17.1、mcp 1.30.0(2.x は `FastMCP` が `MCPServer` に改名されるなど API が変わるので 1.x に固定)、Python 3.12.10
- Console API `POST /console/api/workspaces/current/tool-provider/mcp` で登録し、2 ツールが取り込まれた。詳細は `examples/dify-for-code-first-engineers/verification/tools-mcp.md`
