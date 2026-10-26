"""Dify Service API の疎通確認。

.env の DIFY_API_BASE と DIFY_APP_API_KEY を読み、
POST /v1/chat-messages を blocking モードで 1 回呼んで answer と usage を表示する。
対象: Chatbot / Chatflow アプリ(Legacy Agent は blocking 非対応)。
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# このファイルと同じディレクトリの .env を読む(.env.example をコピーして作る)
load_dotenv(Path(__file__).with_name(".env"))

API_BASE = os.environ.get("DIFY_API_BASE", "http://localhost/v1")
API_KEY = os.environ.get("DIFY_APP_API_KEY")

if not API_KEY:
    sys.exit("DIFY_APP_API_KEY が未設定です。.env を確認してください")

query = sys.argv[1] if len(sys.argv) > 1 else "自己紹介を 1 文でお願いします"

response = httpx.post(
    f"{API_BASE}/chat-messages",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
        "inputs": {},
        "query": query,
        "user": "smoke-test",
        "response_mode": "blocking",
    },
    timeout=120,
)
response.raise_for_status()
body = response.json()

print("answer:", body["answer"])
print("conversation_id:", body["conversation_id"])
print("usage:", json.dumps(body["metadata"]["usage"], ensure_ascii=False, indent=2))
