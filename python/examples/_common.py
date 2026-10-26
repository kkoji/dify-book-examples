"""examples/ 共通: .env の読み込みと DifyClient の生成。

各スクリプトは `python examples/<name>.py` で動く(親ディレクトリの dify_client を import する)。
環境変数(python/.env に書く): DIFY_API_BASE(既定 http://localhost/v1)、DIFY_APP_API_KEY(app- で始まる)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from dify_client import DifyClient  # noqa: E402

load_dotenv(ROOT / ".env")


def make_client(env_key: str = "DIFY_APP_API_KEY") -> DifyClient:
    api_key = os.environ.get(env_key)
    if not api_key:
        sys.exit(f"{env_key} が未設定です。python/.env を確認してください")
    return DifyClient(api_key, base_url=os.environ.get("DIFY_API_BASE", "http://localhost/v1"))
