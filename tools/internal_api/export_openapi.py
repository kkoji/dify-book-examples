"""FastAPI の OpenAPI 仕様を書き出す。Dify に取り込むには servers が必須なので引数で与える。

使い方: python export_openapi.py http://host.docker.internal:8102 > openapi.json
"""

import json
import sys

from main import app

server_url = sys.argv[1] if len(sys.argv) > 1 else "http://host.docker.internal:8102"
spec = app.openapi()
spec["servers"] = [{"url": server_url}]
print(json.dumps(spec, ensure_ascii=False, indent=2))
