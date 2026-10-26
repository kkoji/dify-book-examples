"""Legacy Agent アプリを Service API(POST /v1/chat-messages)で streaming 実行し、
agent_thought(ツール呼び出し)と agent_message(回答の断片)を SSE から表示する。

使い方:
    python stream_agent.py "問い合わせ文"
    python stream_agent.py "続きの質問" --conversation <conversation_id>   # 会話を継続

環境変数(.env に書く): DIFY_API_BASE、DIFY_APP_API_KEY
検証: Dify 1.17.1(セルフホスト)、Ollama qwen2.5:7b、httpx 0.28.1
"""

import argparse
import json
import os
import sys

import httpx
from dotenv import load_dotenv


def iter_sse(response: httpx.Response):
    """SSE の `data:` 行を JSON として順に返す。`event: ping` の裸行は読み飛ばす"""
    for line in response.iter_lines():
        if not line.startswith("data:"):
            continue
        yield json.loads(line[len("data:"):].strip())


def stream_agent(query: str, conversation_id: str = "", user: str = "stream-agent-sample") -> dict:
    load_dotenv()
    base = os.environ.get("DIFY_API_BASE", "http://localhost/v1")
    api_key = os.environ["DIFY_APP_API_KEY"]

    payload = {
        "inputs": {},
        "query": query,
        "user": user,
        "conversation_id": conversation_id,
        "response_mode": "streaming",  # Legacy Agent は streaming のみ
    }
    summary = {"conversation_id": "", "answer": "", "thoughts": 0}
    thoughts: dict[int, dict[str, bool]] = {}
    # ping は約 10 秒ごとに届くので、read timeout はそれより十分長くする
    with httpx.Client(base_url=base, timeout=httpx.Timeout(300.0)) as client:
        with client.stream(
            "POST",
            "/chat-messages",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        ) as response:
            response.raise_for_status()
            for event in iter_sse(response):
                kind = event.get("event")
                if kind == "agent_thought":
                    # 同じ反復(position)の agent_thought は、ツール入力 → ツール結果と
                    # 内容が増えるたびに送り直されるので、増えた分だけ表示する
                    position = event["position"]
                    state = thoughts.setdefault(position, {"header": False, "tool": False, "observation": False})
                    if not state["header"]:
                        print(f"\n[agent_thought #{position}]")
                        state["header"] = True
                    if event.get("tool") and not state["tool"]:
                        print(f"  tool={event['tool']} tool_input={event.get('tool_input')}")
                        state["tool"] = True
                    if event.get("observation") and not state["observation"]:
                        print(f"  observation={event['observation']}")
                        state["observation"] = True
                elif kind == "agent_message":
                    # 回答の断片。連結すると最終回答になる
                    print(event["answer"], end="", flush=True)
                elif kind == "message":
                    # Agent アプリでは最後に完全な回答が message として 1 件届く。追記せず置き換える
                    summary["answer"] = event["answer"]
                elif kind == "message_end":
                    summary["conversation_id"] = event["conversation_id"]
                    usage = event.get("metadata", {}).get("usage", {})
                    print(f"\n[message_end] total_tokens={usage.get('total_tokens')} latency={usage.get('latency')}")
                elif kind == "error":
                    print(f"\n[error] {event.get('code')}: {event.get('message')}")
    summary["thoughts"] = len(thoughts)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query", help="ユーザーの発話")
    parser.add_argument("--conversation", default="", help="継続する会話の conversation_id")
    args = parser.parse_args()

    summary = stream_agent(args.query, conversation_id=args.conversation)
    print(f"\nconversation_id: {summary['conversation_id']}")
    print(f"反復回数(agent_thought の position の数): {summary['thoughts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
