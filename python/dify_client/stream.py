"""SSE イベント列を畳み込むヘルパ。

終端イベントは種別で違う:
  - Chatbot / Legacy Agent / 新 Agent: `message_end`
  - Chatflow: `message_end` の後に `workflow_finished`(両方届く)
  - Workflow: `workflow_finished` のみ
ストリーム開始後の失敗は HTTP 200 のまま `error` イベント(`status`, `code`, `message`)、
またはノード / ワークフローの `status: failed` で届く。
"""

from __future__ import annotations

from collections.abc import Iterable

from .errors import DifyAPIError


def collect_chat(events: Iterable[dict]) -> dict:
    """`/chat-messages` の streaming を最後まで読み、回答と識別子をまとめる。

    `message` / `agent_message` の `answer` を連結する。Agent 系では最後に完全な回答を載せた
    `message` が 1 件届くので、`agent_message` を見た後の `message` は追記せず置き換える。
    """
    result: dict = {
        "answer": "",
        "task_id": None,
        "message_id": None,
        "conversation_id": None,
        "usage": None,
        "workflow_run_id": None,
        "workflow_status": None,
        "events": [],
        "paused": None,  # human_input_required の data
    }
    saw_agent_message = False
    for ev in events:
        name = ev.get("event")
        result["events"].append(name)
        for key in ("task_id", "message_id", "conversation_id"):
            if ev.get(key):
                result[key] = ev[key]
        if name == "agent_message":
            saw_agent_message = True
            result["answer"] += ev.get("answer", "")
        elif name == "message":
            if saw_agent_message:
                result["answer"] = ev.get("answer", "")
            else:
                result["answer"] += ev.get("answer", "")
        elif name == "message_replace":
            result["answer"] = ev.get("answer", "")
        elif name == "message_end":
            result["usage"] = (ev.get("metadata") or {}).get("usage")
        elif name == "workflow_started":
            result["workflow_run_id"] = ev.get("workflow_run_id") or (ev.get("data") or {}).get("id")
        elif name == "workflow_finished":
            result["workflow_status"] = (ev.get("data") or {}).get("status")
        elif name == "human_input_required":
            result["paused"] = ev.get("data")
        elif name == "error":
            raise DifyAPIError(int(ev.get("status", 500)), str(ev.get("code")), str(ev.get("message")))
    return result


def collect_workflow(events: Iterable[dict]) -> dict:
    """`/workflows/run` の streaming を最後まで読み、`workflow_finished.data` と進捗をまとめる。"""
    result: dict = {
        "task_id": None,
        "workflow_run_id": None,
        "status": None,
        "outputs": None,
        "error": None,
        "elapsed_time": None,
        "total_tokens": None,
        "total_steps": None,
        "text": "",  # text_chunk の連結
        "nodes": [],  # node_finished の要約
        "paused": None,
        "events": [],
    }
    for ev in events:
        name = ev.get("event")
        result["events"].append(name)
        for key in ("task_id", "workflow_run_id"):
            if ev.get(key):
                result[key] = ev[key]
        data = ev.get("data") or {}
        if name == "text_chunk":
            result["text"] += data.get("text", "")
        elif name == "node_finished":
            meta = data.get("execution_metadata") or {}
            result["nodes"].append(
                {
                    "node_id": data.get("node_id"),
                    "node_type": data.get("node_type"),
                    "title": data.get("title"),
                    "status": data.get("status"),
                    "elapsed_time": data.get("elapsed_time"),
                    "total_tokens": meta.get("total_tokens"),
                }
            )
        elif name == "workflow_finished":
            for key in ("status", "outputs", "error", "elapsed_time", "total_tokens", "total_steps"):
                result[key] = data.get(key)
        elif name == "workflow_paused":
            result["status"] = data.get("status", "paused")
        elif name == "human_input_required":
            result["paused"] = data
        elif name == "error":
            raise DifyAPIError(int(ev.get("status", 500)), str(ev.get("code")), str(ev.get("message")))
    return result
