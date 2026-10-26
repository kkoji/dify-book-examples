"""Human Input で止まった Chatflow をフォーム API で再開する最小例。

使い方: python examples/human_input_resume.py "問い合わせ文"
対象: chatflow 章の support-chatflow-human-input(Delivery Method が Webapp のもの)
"""

import sys

from _common import make_client

from dify_client import collect_chat

USER = "service-api-human-input"


def main(question: str) -> int:
    with make_client() as dify:
        res = collect_chat(dify.chat_stream(question, user=USER))
        print("events:", " ".join(res["events"]))
        print("answer so far:", res["answer"].strip())
        if not res["paused"]:
            print("Human Input に入らず完走した(needs_human が偽)")
            return 0

        form_token = res["paused"]["form_token"]
        form = dify.human_input_form(form_token)
        print("form_content:", form["form_content"].strip()[:120])
        print("user_actions:", [(a["id"], a["title"]) for a in form["user_actions"]])

        # inputs のキーは入力欄の output_variable_name、action は user_actions[].id
        print("submit ->", dify.submit_human_input(
            form_token, user=USER, action="approve", inputs={"comment": "総務部に確認済みです。"},
        ))

        # 再開後のイベントは run の events で購読する(user は開始時と同じ)
        for ev in dify.workflow_events(res["workflow_run_id"], user=USER):
            name = ev["event"]
            data = ev.get("data") or {}
            if name == "node_finished":
                print(f"  node_finished {data['title']} {data['status']}")
            elif name in ("workflow_started", "human_input_form_filled", "message_end", "workflow_finished"):
                print(f"  {name} {data.get('reason') or data.get('status') or ''}")
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "来週のオフィス移転で、私の席がどこになるか教えてください。"))
