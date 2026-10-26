"""停止と再接続: Workflow を streaming で始めて途中で止める / 切断して events で購読し直す。

使い方:
    python examples/stop_and_resubscribe.py stop        # 2 つ目の node_started で POST /workflows/tasks/{task_id}/stop
    python examples/stop_and_resubscribe.py resubscribe # workflow_started を受けたら切断し、GET /workflow/{run_id}/events で再購読
対象: 長めの Workflow(workflow-control-flow 章の loop-refine など)
"""

import sys
import time

from _common import make_client

USER = "service-api-stop"
QUESTION = "ノート PC の電源が入らなくなりました。昨日までは使えていました。"


def stop(dify) -> None:
    started = 0
    for ev in dify.run_workflow_stream({"question": QUESTION}, user=USER):
        name = ev["event"]
        if name == "node_started":
            started += 1
            print(f"node_started #{started} {ev['data']['title']}")
            if started == 2:
                # 停止は streaming 中だけ有効。Workflow は user が一致しなくてもよい
                print("stop ->", dify.stop_workflow(ev["task_id"], user=USER))
        elif name == "workflow_finished":
            print(f"workflow_finished status={ev['data']['status']} steps={ev['data']['total_steps']}")
        elif name == "error":
            print("error", ev.get("code"), ev.get("message"))
    # 停止後の状態は GET /workflows/run/{id} でも取れる
    run = dify.workflow_run(ev["workflow_run_id"])
    print(f"workflow_run status={run['status']} error={run['error']!r}")


def resubscribe(dify) -> None:
    run_id = None
    events = dify.run_workflow_stream({"question": QUESTION}, user=USER)
    for ev in events:
        if ev["event"] == "workflow_started":
            run_id = ev["workflow_run_id"]
            print(f"workflow_started run_id={run_id}; クライアント側で切断する")
            break
    events.close()  # ジェネレータを閉じる = HTTP 接続を切る。実行はサーバー側で続く

    time.sleep(5)
    print("resubscribe (include_state_snapshot=true)")
    # user は開始時と同じでなければならない。include_state_snapshot で実行済みノードが先頭で再生される
    for ev in dify.workflow_events(run_id, user=USER, include_state_snapshot=True):
        name = ev["event"]
        data = ev.get("data") or {}
        if name in ("node_started", "node_finished"):
            print(f"  {name:<14} {data.get('title')} {data.get('status', '')}")
        elif name in ("workflow_started", "workflow_finished", "workflow_paused"):
            print(f"  {name:<14} status={data.get('status')} reason={data.get('reason')}")
        elif name == "error":
            print("  error", ev.get("code"), ev.get("message"))


def main(cmd: str) -> None:
    with make_client() as dify:
        {"stop": stop, "resubscribe": resubscribe}[cmd](dify)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "stop")
