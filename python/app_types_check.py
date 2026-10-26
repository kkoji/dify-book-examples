"""app-types 章: アプリ種別を GET /v1/info で確かめ、種別に応じた入口で 1 回実行する。

使い方:
    DIFY_APP_API_KEY=app-xxxx python app_types_check.py "有給休暇の申請はいつまでに出せばよいですか?"

環境変数(.env でも可):
    DIFY_API_BASE  省略時 http://localhost/v1
    DIFY_APP_API_KEY   アプリの API キー(app- で始まる)
"""

import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE = os.environ.get("DIFY_API_BASE", "http://localhost/v1")
KEY = os.environ["DIFY_APP_API_KEY"]
HEADERS = {"Authorization": f"Bearer {KEY}"}
USER = "app-types-check"


def main(question: str) -> None:
    with httpx.Client(base_url=BASE, headers=HEADERS, timeout=120) as client:
        info = client.get("/info").raise_for_status().json()
        mode = info["mode"]
        print(f"name={info['name']} mode={mode}")

        if mode in ("chat", "advanced-chat"):
            # Chatbot / Chatflow: 会話を持つので query と conversation_id を扱う
            res = client.post(
                "/chat-messages",
                json={"inputs": {}, "query": question, "user": USER, "response_mode": "blocking"},
            ).raise_for_status().json()
            print(f"conversation_id={res['conversation_id']}")
            print(f"answer={res['answer']}")
        elif mode == "workflow":
            # Workflow: 1 回実行。入力は User Input ノードの変数名で渡す
            res = client.post(
                "/workflows/run",
                json={"inputs": {"question": question}, "user": USER, "response_mode": "blocking"},
            ).raise_for_status().json()
            print(f"workflow_run_id={res['workflow_run_id']} status={res['data']['status']}")
            print(f"answer={res['data']['outputs']['answer']}")
        else:
            # completion / agent-chat / agent はこの章では扱わない
            print(f"unsupported mode in this script: {mode}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "有給休暇の申請はいつまでに出せばよいですか?")
