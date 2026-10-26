from typing import Any

from dify_plugin import ToolProvider


class OfficeHoursProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        # 資格情報を使わないので検証は不要
        return
