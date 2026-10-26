"""ユーザーフィードバックとワークフロー実行ログを Service API で取り出し、JSON Lines に書き出す。

評価ループの材料集め用。like / dislike の付いたメッセージや、失敗した実行をテストケース候補として眺める。
アプリ種別で取れるものが違う:
  - チャット系(Chatbot / Chatflow / Legacy Agent): GET /app/feedbacks(全ユーザーのフィードバック)
  - Workflow: GET /workflows/logs(実行単位のサマリ。status で failed だけに絞れる)
会話そのものはエンドユーザー単位(user)でしか取れないので、GET /conversations と GET /messages は --user を指定したときだけ使う。

使い方:
    python export_feedback.py feedbacks --out feedbacks.jsonl            # チャット系アプリのキーで
    python export_feedback.py workflow-logs --status failed --out failed.jsonl   # Workflow アプリのキーで
    python export_feedback.py messages --user some-end-user --out messages.jsonl # 指定ユーザーの会話とメッセージ

環境変数(.env に書く): DIFY_API_BASE、DIFY_APP_API_KEY
検証: Dify 1.17.1(セルフホスト)、httpx 0.28.1
"""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

API_BASE = os.environ.get("DIFY_API_BASE", "http://localhost/v1")
API_KEY = os.environ.get("DIFY_APP_API_KEY")


def client() -> httpx.Client:
    return httpx.Client(base_url=API_BASE, headers={"Authorization": f"Bearer {API_KEY}"}, timeout=60)


def iter_feedbacks(c: httpx.Client, limit: int = 100):
    """GET /app/feedbacks をページングして 1 件ずつ返す(応答に has_more が無いので空ページで止める)"""
    page = 1
    while True:
        r = c.get("/app/feedbacks", params={"page": page, "limit": limit})
        r.raise_for_status()
        data = r.json()["data"]
        if not data:
            return
        yield from data
        if len(data) < limit:
            return
        page += 1


def iter_workflow_logs(c: httpx.Client, status: str | None, limit: int = 100):
    """GET /workflows/logs をページングして 1 件ずつ返す。status は succeeded / failed / stopped"""
    page = 1
    while True:
        params = {"page": page, "limit": limit}
        if status:
            params["status"] = status
        r = c.get("/workflows/logs", params=params)
        r.raise_for_status()
        body = r.json()
        yield from body["data"]
        if not body.get("has_more"):
            return
        page += 1


def iter_messages(c: httpx.Client, user: str, limit: int = 100):
    """指定ユーザーの会話を GET /conversations で辿り、各会話のメッセージを GET /messages で返す"""
    last_id = None
    while True:
        params = {"user": user, "limit": limit}
        if last_id:
            params["last_id"] = last_id
        r = c.get("/conversations", params=params)
        r.raise_for_status()
        body = r.json()
        for conv in body["data"]:
            m = c.get("/messages", params={"conversation_id": conv["id"], "user": user, "limit": limit})
            m.raise_for_status()
            for msg in m.json()["data"]:
                yield {"conversation": conv, "message": msg}
        if not body.get("has_more") or not body["data"]:
            return
        last_id = body["data"][-1]["id"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p1 = sub.add_parser("feedbacks", help="GET /app/feedbacks")
    p1.add_argument("--out", default="-")
    p2 = sub.add_parser("workflow-logs", help="GET /workflows/logs")
    p2.add_argument("--status", choices=["succeeded", "failed", "stopped"], default=None)
    p2.add_argument("--out", default="-")
    p3 = sub.add_parser("messages", help="GET /conversations + GET /messages(user 必須)")
    p3.add_argument("--user", required=True)
    p3.add_argument("--out", default="-")
    args = parser.parse_args()

    if not API_KEY:
        sys.exit("DIFY_APP_API_KEY が未設定です。.env を確認してください")

    with client() as c:
        if args.command == "feedbacks":
            rows = iter_feedbacks(c)
        elif args.command == "workflow-logs":
            rows = iter_workflow_logs(c, args.status)
        else:
            rows = iter_messages(c, args.user)

        out = sys.stdout if args.out == "-" else open(args.out, "w", encoding="utf-8")
        count = 0
        try:
            for row in rows:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += 1
        finally:
            if out is not sys.stdout:
                out.close()
    print(f"{count} rows", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
