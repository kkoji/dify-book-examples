"""Dify アプリを公開した MCP サーバーへ、公式 mcp パッケージのクライアントで initialize → tools/list → tools/call を送る。

使い方:
    python mcp_call_dify.py "問い合わせ文"

環境変数(.env に書く): DIFY_MCP_SERVER_URL(例: http://localhost/mcp/server/<server_code>/mcp)
URL 自体が認証情報なので、.env に置きリポジトリにコミットしない。
検証: Dify 1.17.1(セルフホスト)、mcp 1.30.0
"""

import asyncio
import json
import os
import sys

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def run(question: str) -> int:
    load_dotenv()
    url = os.environ["DIFY_MCP_SERVER_URL"]
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"server: {init.serverInfo.name} {init.serverInfo.version}  protocol: {init.protocolVersion}")
            print(f"instructions: {init.instructions}")

            tools = await session.list_tools()
            for tool in tools.tools:
                print(f"tool: {tool.name}")
                print(f"  inputSchema: {json.dumps(tool.inputSchema, ensure_ascii=False)}")
            if not tools.tools:
                print("no tools")
                return 1

            # Dify はアプリ 1 つにつきツール 1 つ(名前はアプリ名)を公開する
            tool_name = tools.tools[0].name
            result = await session.call_tool(tool_name, {"question": question})
            print(f"isError: {result.isError}")
            for content in result.content:
                if content.type == "text":
                    print("text:", content.text)
            if result.structuredContent is not None:
                print("structuredContent:", json.dumps(result.structuredContent, ensure_ascii=False))
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    return asyncio.run(run(sys.argv[1]))


if __name__ == "__main__":
    sys.exit(main())
