"""公開済みの新 Agent(mode: agent)を Service API(POST /v1/chat-messages)で streaming 実行し、
SSE に流れるイベント(agent_thought、agent_message、message、message_end など)を順に表示する。

使い方:
    python stream_new_agent.py "依頼文"
    python stream_new_agent.py "続きの依頼" --conversation <conversation_id>   # 会話を継続
    python stream_new_agent.py "依頼文" --raw                                   # 全イベントの生 JSON を表示

環境変数(.env に書く): DIFY_API_BASE、DIFY_APP_API_KEY(新 Agent の Access Point で発行した app- キー)
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


def stream_new_agent(query: str, conversation_id: str = "", user: str = "stream-new-agent-sample", raw: bool = False) -> dict:
    load_dotenv()
    base = os.environ.get("DIFY_API_BASE", "http://localhost/v1")
    api_key = os.environ["DIFY_APP_API_KEY"]

    payload = {
        "inputs": {},
        "query": query,
        "user": user,
        "conversation_id": conversation_id,
        "response_mode": "streaming",  # 新 Agent は streaming のみ(blocking は 400)
    }
    summary = {"conversation_id": "", "answer": "", "events": []}
    thoughts: dict[int, dict[str, bool]] = {}
    # 新 Agent はサンドボックスでの作業を含むので 1 回の応答が長い。read timeout は長めにとる
    with httpx.Client(base_url=base, timeout=httpx.Timeout(600.0)) as client:
        with client.stream(
            "POST",
            "/chat-messages",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        ) as response:
            response.raise_for_status()
            for event in iter_sse(response):
                kind = event.get("event")
                summary["events"].append(kind)
                if kind == "message_end":
                    summary["conversation_id"] = event.get("conversation_id", "")
                if raw:
                    print(json.dumps(event, ensure_ascii=False))
                    continue
                if kind == "agent_thought":
                    # Legacy Agent と同じく、同じ position の agent_thought が内容の増加に応じて送り直される前提で増分だけ表示する
                    position = event.get("position", 0)
                    state = thoughts.setdefault(position, {"header": False, "tool": False, "observation": False})
                    if not state["header"]:
                        print(f"\n[agent_thought #{position}] thought={event.get('thought', '')[:80]!r}")
                        state["header"] = True
                    if event.get("tool") and not state["tool"]:
                        print(f"  tool={event['tool']} tool_input={event.get('tool_input')}")
                        state["tool"] = True
                    if event.get("observation") and not state["observation"]:
                        print(f"  observation={str(event['observation'])[:200]}")
                        state["observation"] = True
                elif kind == "agent_message":
                    # 回答の断片。連結すると最終回答になる
                    print(event.get("answer", ""), end="", flush=True)
                elif kind == "message":
                    # 最後に完全な回答が message として 1 件届く(Legacy Agent と同じ)。追記せず置き換える
                    summary["answer"] = event.get("answer", "")
                elif kind == "message_file":
                    print(f"\n[message_file] type={event.get('type')} url={event.get('url')}")
                elif kind == "message_end":
                    usage = event.get("metadata", {}).get("usage", {})
                    print(f"\n[message_end] total_tokens={usage.get('total_tokens')} latency={usage.get('latency')}")
                elif kind == "error":
                    print(f"\n[error] {event.get('code')}: {event.get('message')}")
                else:
                    print(f"\n[{kind}] {json.dumps({k: v for k, v in event.items() if k not in ('event',)}, ensure_ascii=False)[:200]}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query", help="ユーザーの依頼")
    parser.add_argument("--conversation", default="", help="継続する会話の conversation_id")
    parser.add_argument("--raw", action="store_true", help="全イベントの生 JSON を表示する")
    args = parser.parse_args()

    summary = stream_new_agent(args.query, conversation_id=args.conversation, raw=args.raw)
    print(f"\nconversation_id: {summary['conversation_id']}")
    # 届いたイベント名の順序(重複を畳んで表示)
    folded = [k for i, k in enumerate(summary["events"]) if i == 0 or summary["events"][i - 1] != k]
    print(f"event 順序: {' -> '.join(str(k) for k in folded)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
