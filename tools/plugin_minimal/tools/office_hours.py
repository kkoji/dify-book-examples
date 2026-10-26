from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

OFFICE_HOURS = {
    "tokyo": "平日 9:00-18:00(総務受付は 3F)",
    "osaka": "平日 9:30-17:30(受付は 2F)",
}


class OfficeHoursTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        location = str(tool_parameters.get("location", "")).lower()
        hours = OFFICE_HOURS.get(location, "該当する拠点がありません")
        # 人向けのテキストと、ワークフローで変数として使える値の両方を返す
        yield self.create_text_message(hours)
        yield self.create_variable_message("hours", hours)
