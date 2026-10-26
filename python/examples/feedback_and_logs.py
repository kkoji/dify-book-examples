"""フィードバックとログの取り出し: messages/{id}/feedbacks, app/feedbacks, workflows/logs, workflows/run/{id}。

使い方:
    python examples/feedback_and_logs.py feedback   # Chatbot / Chatflow のキー: 1 ターン送って like を付け、一覧を見る
    python examples/feedback_and_logs.py logs       # Workflow のキー: 直近の実行サマリと 1 件の詳細
"""

import json
import sys

from _common import make_client

USER = "service-api-feedback"


def feedback(dify) -> None:
    res = dify.chat("有給休暇の申請はいつまでに出せばよいですか。", user=USER)
    message_id = res["message_id"]
    print("answer:", res["answer"].strip()[:80])
    print("like ->", dify.feedback(message_id, user=USER, rating="like", content="締め切りが明確"))
    page = dify.app_feedbacks(limit=5)  # 全 user 横断。応答は {"data": [...]} だけで総数は無い
    for f in page["data"]:
        print(f"  {f['message_id'][:8]} rating={f['rating']} content={f['content']!r} from={f['from_source']}")
    print("cancel ->", dify.feedback(message_id, user=USER, rating=None))


def logs(dify) -> None:
    page = dify.workflow_logs(limit=5)  # status は succeeded / failed / stopped のみ指定できる
    print(f"total={page['total']} has_more={page['has_more']}")
    for row in page["data"]:
        run = row["workflow_run"]
        end_user = (row.get("created_by_end_user") or {}).get("session_id")
        print(f"  {run['id'][:8]} v={run['version']} status={run['status']} steps={run['total_steps']} "
              f"tokens={run['total_tokens']} elapsed={run['elapsed_time']:.1f}s user={end_user}")
    run_id = page["data"][0]["workflow_run"]["id"]
    detail = dify.workflow_run(run_id)
    inputs = json.loads(detail["inputs"])  # inputs は JSON 文字列で返る
    print(f"detail {run_id[:8]}: status={detail['status']} inputs={inputs} outputs={detail['outputs']}")


def main(cmd: str) -> None:
    with make_client() as dify:
        {"feedback": feedback, "logs": logs}[cmd](dify)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "feedback")
