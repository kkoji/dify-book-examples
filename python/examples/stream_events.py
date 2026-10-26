"""streaming で呼ぶ: SSE をジェネレータで受け取り、ノード単位の進捗とテキスト断片を表示する。

使い方: python examples/stream_events.py "問い合わせ文"
Chatbot / Chatflow / Workflow / Legacy Agent のどのキーでも動く(mode で入口を切り替える)。
"""

import sys
import time

from _common import make_client

USER = "service-api-stream"


def show(events) -> dict:
    """イベントを表示しながら読み切り、終端の情報を返す。"""
    t0 = time.monotonic()
    answer = ""
    last: dict = {}
    for ev in events:
        name = ev["event"]
        t = time.monotonic() - t0
        data = ev.get("data") or {}
        if name == "node_started":
            print(f"[{t:5.1f}s] node_started  {data['node_type']:<20} {data['title']}")
        elif name == "node_finished":
            meta = data.get("execution_metadata") or {}
            print(f"[{t:5.1f}s] node_finished {data['node_type']:<20} {data['title']} "
                  f"status={data['status']} elapsed={data.get('elapsed_time', 0):.2f}s tokens={meta.get('total_tokens')}")
        elif name in ("message", "agent_message"):
            answer += ev["answer"]  # 回答の断片
        elif name == "text_chunk":
            answer += data["text"]  # Workflow の Output に向かう文字列の断片
        elif name == "agent_thought":
            print(f"[{t:5.1f}s] agent_thought #{ev['position']} tool={ev.get('tool')!r}")
        elif name == "message_end":
            print(f"[{t:5.1f}s] message_end usage={ (ev.get('metadata') or {}).get('usage') }")
        elif name == "workflow_finished":
            print(f"[{t:5.1f}s] workflow_finished status={data['status']} steps={data['total_steps']} tokens={data['total_tokens']}")
        elif name == "error":
            # ストリーム開始後の失敗。HTTP は 200 のままなのでここで拾う
            print(f"[{t:5.1f}s] error code={ev.get('code')} message={ev.get('message')}")
        last = ev
    print("answer:", answer.strip())
    return last


def main(question: str) -> None:
    with make_client() as dify:
        mode = dify.info()["mode"]
        if mode == "workflow":
            events = dify.run_workflow_stream({"question": question}, user=USER)
        else:
            events = dify.chat_stream(question, user=USER)
        last = show(events)
        print("last event:", last.get("event"), "task_id:", last.get("task_id"))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "先週の出張で立て替えたタクシー代はどうやって精算すればいいですか。")
