"""Workflow アプリを Service API(POST /v1/workflows/run)で blocking 実行し、outputs を表示する。

使い方:
    python run_workflow.py "問い合わせ文"
    python run_workflow.py --var questions "1 行目\n2 行目"   # 入力変数名を変える

環境変数(.env に書く): DIFY_API_BASE、DIFY_APP_API_KEY
検証: Dify 1.17.1(セルフホスト)、Ollama qwen3:8b、httpx 0.28.1
"""

import argparse
import json
import os
import sys

import httpx
from dotenv import load_dotenv


def run_workflow(
    question: str,
    variable: str = "question",
    user: str = "run-workflow-sample",
    extra_inputs: dict | None = None,
) -> dict:
    load_dotenv()
    base = os.environ.get("DIFY_API_BASE", "http://localhost/v1")
    api_key = os.environ["DIFY_APP_API_KEY"]

    payload = {
        "inputs": {variable: question, **(extra_inputs or {})},
        "response_mode": "blocking",
        "user": user,
    }
    with httpx.Client(base_url=base, timeout=httpx.Timeout(300.0)) as client:
        response = client.post(
            "/workflows/run",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("question", help="入力変数に渡す文字列")
    parser.add_argument("--var", default="question", help="User Input ノードの変数名(既定: question)")
    parser.add_argument("--input", action="append", default=[], metavar="NAME=VALUE", help="追加の入力変数(複数可)")
    args = parser.parse_args()

    extra = dict(item.split("=", 1) for item in args.input)
    result = run_workflow(args.question.replace("\\n", "\n"), variable=args.var, extra_inputs=extra)
    data = result["data"]
    print(f"workflow_run_id: {result['workflow_run_id']}")
    print(f"status: {data['status']}  elapsed: {data['elapsed_time']:.2f}s  steps: {data['total_steps']}")
    # partial-succeeded は、Fail Branch などで一部ノードが失敗しつつ Output まで到達した状態。
    # outputs は返るので表示し、終了コードで区別する
    if data["status"] not in ("succeeded", "partial-succeeded"):
        print(f"error: {data.get('error')}")
        return 1
    if data["status"] == "partial-succeeded":
        print("warning: 一部のノードが失敗しました(outputs の error_type などを確認してください)")
    print("outputs:")
    print(json.dumps(data["outputs"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
