"""blocking で呼ぶ: /chat-messages または /workflows/run を mode に応じて 1 回呼ぶ。

使い方: python examples/blocking_call.py "問い合わせ文"
Legacy Agent / 新 Agent のキーで実行すると 400 になることも確かめられる。
"""

import json
import sys

from _common import make_client

from dify_client import DifyAPIError

USER = "service-api-blocking"


def main(question: str) -> int:
    with make_client() as dify:
        mode = dify.info()["mode"]
        try:
            if mode == "workflow":
                res = dify.run_workflow({"question": question}, user=USER)
                data = res["data"]
                print(f"workflow_run_id={res['workflow_run_id']} task_id={res['task_id']}")
                print(f"status={data['status']} elapsed={data['elapsed_time']:.1f}s steps={data['total_steps']} tokens={data['total_tokens']}")
                # succeeded 以外に partial-succeeded(例外分岐を通った)もある。failed だけを失敗にする
                if data["status"] == "failed":
                    print(f"error={data['error']}")
                    return 1
                print(json.dumps(data["outputs"], ensure_ascii=False, indent=2))
            else:
                res = dify.chat(question, user=USER)
                print(f"conversation_id={res['conversation_id']} message_id={res['message_id']} task_id={res['task_id']}")
                print(f"answer={res['answer']}")
                print("usage=", json.dumps(res["metadata"]["usage"], ensure_ascii=False))
        except DifyAPIError as e:
            # エラー応答は {code, message, status} の 3 フィールド
            print(f"error: status={e.status} code={e.code} message={e.message}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "社内 Wi-Fi に接続できなくなりました。"))
