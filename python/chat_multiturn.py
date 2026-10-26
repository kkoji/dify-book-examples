"""Chatflow アプリを Service API(POST /v1/chat-messages)で streaming 実行し、conversation_id を引き継いで多ターン送る。

使い方:
    python chat_multiturn.py                       # 既定の 3 ターンを送る
    python chat_multiturn.py "1 ターン目" "2 ターン目"   # 任意の発話を順に送る

環境変数(.env に書く): DIFY_API_BASE、DIFY_APP_API_KEY
検証: Dify 1.17.1(セルフホスト)、Ollama qwen2.5:7b、httpx 0.28.1
"""

import json
import os
import sys
from collections.abc import Iterator

import httpx
from dotenv import load_dotenv

DEFAULT_TURNS = [
    "経理部の田中です。先週の出張で立て替えたタクシー代はどうやって精算すればいいですか。",
    "領収書をなくした場合はどうすればいいですか。",
    "ところで来月の有給休暇の申請締め切りはいつですか。",
]


def iter_sse(client: httpx.Client, api_key: str, payload: dict) -> Iterator[dict]:
    """SSE を 1 イベントずつ dict で返す。`event: ping` の裸行は読み飛ばす。"""
    headers = {"Authorization": f"Bearer {api_key}"}
    with client.stream("POST", "/chat-messages", headers=headers, json=payload) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line.startswith("data: "):
                yield json.loads(line[len("data: "):])


def send_turn(client: httpx.Client, api_key: str, query: str, conversation_id: str, user: str) -> str:
    payload = {
        "inputs": {},
        "query": query,
        "user": user,
        "response_mode": "streaming",
        "conversation_id": conversation_id,  # 空文字なら新規会話
    }
    answer = ""
    seen: list[str] = []
    for event in iter_sse(client, api_key, payload):
        name = event["event"]
        if name not in seen:
            seen.append(name)
        if name == "message":
            answer += event["answer"]
            conversation_id = event["conversation_id"]
        elif name == "human_input_required":
            # 担当者の確認待ちで一時停止した。フォームの扱いは service-api 章で扱う
            print(f"  [paused] form_token={event['data']['form_token']}")
        elif name == "error":
            raise RuntimeError(f"{event.get('code')}: {event.get('message')}")
    print(f"  events: {' '.join(seen)}")
    print(f"  answer: {answer.strip()}")
    return conversation_id


def main() -> int:
    load_dotenv()
    base = os.environ.get("DIFY_API_BASE", "http://localhost/v1")
    api_key = os.environ["DIFY_APP_API_KEY"]
    turns = sys.argv[1:] or DEFAULT_TURNS

    conversation_id = ""
    with httpx.Client(base_url=base, timeout=httpx.Timeout(300.0)) as client:
        for index, query in enumerate(turns, start=1):
            print(f"turn {index}: {query}")
            conversation_id = send_turn(client, api_key, query, conversation_id, user="chat-multiturn-sample")
            print(f"  conversation_id: {conversation_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
