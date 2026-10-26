"""Dify Service API を httpx で薄く包んだクライアント(service-api 章)。

検証: Dify 1.17.1(セルフホスト、Docker Compose)、httpx 0.28.1

使い方:
    from dify_client import DifyClient
    with DifyClient(api_key="app-...", base_url="http://localhost/v1") as dify:
        print(dify.info()["mode"])
"""

from .client import DifyClient
from .errors import DifyAPIError
from .sse import iter_sse
from .stream import collect_chat, collect_workflow

__all__ = ["DifyClient", "DifyAPIError", "iter_sse", "collect_chat", "collect_workflow"]
