"""Streamable HTTP の最小 MCP サーバー(公式 mcp パッケージ 1.30.0)。Dify に外部 MCP サーバーとして登録する題材。

ツール:
    get_office_hours(location)  拠点の受付時間を返す
    lookup_policy(topic)        社内規程の要約を返す

起動: python server.py  (http://0.0.0.0:8103/mcp で待ち受ける)
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("internal-helpdesk", host="0.0.0.0", port=8103)

OFFICE_HOURS = {
    "tokyo": "平日 9:00-18:00(総務受付は 3F)",
    "osaka": "平日 9:30-17:30(受付は 2F)",
}
POLICIES = {
    "expense": "経費は申請システムから月末までに申請し、領収書の原本を総務へ提出します。",
    "leave": "有給休暇は取得日の 3 営業日前までに勤怠システムで申請し、上長の承認を受けます。",
}


@mcp.tool()
def get_office_hours(location: str) -> str:
    """拠点名(tokyo / osaka)から受付時間を返す。"""
    return OFFICE_HOURS.get(location.lower(), "該当する拠点がありません")


@mcp.tool()
def lookup_policy(topic: str) -> str:
    """規程のトピック(expense / leave)から要約を返す。"""
    return POLICIES.get(topic.lower(), "該当する規程がありません")


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
