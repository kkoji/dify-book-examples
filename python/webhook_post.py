"""Webhook Trigger の URL へ JSON を POST して Workflow を起動する。

使い方:
    python webhook_post.py "問い合わせ文"

環境変数(.env に書く): DIFY_WEBHOOK_URL(Webhook Trigger ノードに表示される本番 URL。
  セルフホストでは <TRIGGER_URL>/triggers/webhook/<webhook_id> の形)
Webhook は非同期で、レスポンスは受理の応答(既定 200)だけ。実行結果はアプリのログで確認する。
検証: Dify 1.17.1(セルフホスト)、httpx 0.28.1
"""

import os
import sys

import httpx
from dotenv import load_dotenv


def post_webhook(question: str) -> httpx.Response:
    load_dotenv()
    url = os.environ["DIFY_WEBHOOK_URL"]
    with httpx.Client(timeout=httpx.Timeout(30.0)) as client:
        return client.post(url, json={"question": question})


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    response = post_webhook(sys.argv[1])
    print(f"status: {response.status_code}")
    print(f"body: {response.text}")
    return 0 if response.is_success else 1


if __name__ == "__main__":
    sys.exit(main())
