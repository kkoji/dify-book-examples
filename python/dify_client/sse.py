"""Server-Sent Events(SSE)を 1 イベントずつ dict にして返す。

Dify の SSE は `data: ` 行に JSON オブジェクトが 1 件、イベント同士は空行で区切られる。
`ping` だけは `data:` のない `event: ping` の裸行で、Chatflow / Workflow では
ストリームの先頭と、以後およそ 10 秒ごとに届く(keep-alive)。
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx


def iter_sse(response: httpx.Response, *, include_ping: bool = False) -> Iterator[dict]:
    """httpx のストリーム応答から SSE イベントを順に yield する。

    - `data:` を持つフレームは JSON として返す(Dify のイベントは `event` キーで種別が分かる)
    - `event: ping` の裸行は既定で読み飛ばす。`include_ping=True` なら `{"event": "ping"}` を返す
    """
    event_name: str | None = None
    data_lines: list[str] = []
    for line in response.iter_lines():
        if line == "":
            # 空行 = フレームの終わり
            if data_lines:
                yield json.loads("\n".join(data_lines))
            elif event_name == "ping" and include_ping:
                yield {"event": "ping"}
            event_name = None
            data_lines = []
            continue
        if line.startswith(":"):
            continue  # コメント行
        field, _, value = line.partition(":")
        value = value.removeprefix(" ")
        if field == "data":
            data_lines.append(value)
        elif field == "event":
            event_name = value
    if data_lines:  # 末尾に空行が無いまま閉じた場合
        yield json.loads("\n".join(data_lines))
