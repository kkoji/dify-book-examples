"""LangGraph のグラフから Dify の Workflow を 1 ノードとして呼ぶ例。

Dify を「API で呼ばれる部品」として扱い、オーケストレーションは LangGraph 側が持つ。
呼ぶのは workflow 章の support-triage(`POST /v1/workflows/run`、blocking)。
分類と回答案は Dify に任せ、`needs_human` による振り分けと後処理は LangGraph の条件付きエッジで行う。

    python langgraph_calls_dify.py "問い合わせ文"

環境変数(.env): DIFY_API_BASE、DIFY_APP_API_KEY(support-triage の app- キー)
検証: Dify 1.17.1、langgraph 1.2.12、httpx 0.28.1
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Literal, TypedDict

import httpx
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

load_dotenv(Path(__file__).with_name(".env"))

API_BASE = os.environ.get("DIFY_API_BASE", "http://localhost/v1")
API_KEY = os.environ.get("DIFY_APP_API_KEY")
USER = "langgraph-hybrid"


class TriageState(TypedDict, total=False):
    question: str
    workflow_run_id: str
    status: str          # succeeded / failed / stopped / partial-succeeded
    category: str
    answer: str
    needs_human: bool
    reply: str           # このグラフの最終出力


def call_dify(state: TriageState) -> TriageState:
    """Dify Workflow を blocking で呼ぶノード。`data.status` と `data.outputs` を state に写す。"""
    response = httpx.post(
        f"{API_BASE}/workflows/run",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"inputs": {"question": state["question"]}, "user": USER, "response_mode": "blocking"},
        timeout=httpx.Timeout(connect=10.0, read=600.0, write=30.0, pool=10.0),
    )
    response.raise_for_status()
    body = response.json()
    data = body["data"]
    if data["status"] == "failed":  # partial-succeeded は結果として扱う(workflow-control-flow 章)
        raise RuntimeError(f"Dify workflow failed: {data.get('error')}")
    outputs = data.get("outputs") or {}
    return {
        "workflow_run_id": body["workflow_run_id"],
        "status": data["status"],
        "category": str(outputs.get("category", "")),
        "answer": str(outputs.get("answer", "")),
        "needs_human": bool(outputs.get("needs_human", True)),
    }


def route(state: TriageState) -> Literal["escalate", "auto_reply"]:
    """Dify の出力 `needs_human` で分岐する。LangGraph 側の条件付きエッジ。"""
    return "escalate" if state.get("needs_human") else "auto_reply"


def escalate(state: TriageState) -> TriageState:
    # 本来はチケット起票や Slack 通知など。ここでは文面を作るだけ
    return {"reply": f"[{state['category']}] 担当者が確認して折り返します。回答案: {state['answer']}"}


def auto_reply(state: TriageState) -> TriageState:
    return {"reply": f"[{state['category']}] {state['answer']}"}


builder = StateGraph(TriageState)
builder.add_node("call_dify", call_dify)
builder.add_node("escalate", escalate)
builder.add_node("auto_reply", auto_reply)
builder.add_edge(START, "call_dify")
builder.add_conditional_edges("call_dify", route)
builder.add_edge("escalate", END)
builder.add_edge("auto_reply", END)
graph = builder.compile()


def main() -> int:
    if not API_KEY:
        print("DIFY_APP_API_KEY が未設定です。.env を確認してください", file=sys.stderr)
        return 1
    question = sys.argv[1] if len(sys.argv) > 1 else "先週の出張で立て替えたタクシー代はどうやって精算すればいいですか。"
    result = graph.invoke({"question": question})
    print(json.dumps(
        {k: result.get(k) for k in ("workflow_run_id", "status", "category", "needs_human", "reply")},
        ensure_ascii=False, indent=2,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
