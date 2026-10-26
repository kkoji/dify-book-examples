"""Knowledge API でナレッジを作り、ディレクトリ内の Markdown を一括投入してメタデータを付ける。

使い方:
    python knowledge_ingest.py ../data/policies --name "knowledge: policies"
    python knowledge_ingest.py ../data/policies --separator "\\n\\n" --max-tokens 500 --overlap 50

手順(すべて /v1/datasets 配下の Knowledge API):
    1. POST /datasets                         ナレッジを作る(High Quality、埋め込みモデルを指定)
    2. POST /datasets/{id}/metadata           メタデータフィールド department(string)と effective_date(time)を作る
    3. POST /datasets/{id}/document/create-by-file   ファイルごとに投入(General チャンク、区切りと最大長を指定)
    4. GET  /datasets/{id}/documents/{batch}/indexing-status   completed になるまでポーリング
    5. POST /datasets/{id}/documents/metadata   フロントマターの値をメタデータとして付与

環境変数(.env に書く): DIFY_API_BASE、DIFY_KNOWLEDGE_API_KEY
検証: Dify 1.17.1(セルフホスト)、Ollama nomic-embed-text、httpx 0.28.1
"""

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

EMBEDDING_PROVIDER = os.environ.get("DIFY_EMBEDDING_PROVIDER", "langgenius/ollama/ollama")
EMBEDDING_MODEL = os.environ.get("DIFY_EMBEDDING_MODEL", "nomic-embed-text")


def parse_frontmatter(text: str) -> dict:
    """先頭の --- ... --- を key: value の辞書として読む(値は文字列のまま)"""
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}
    meta = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip('"')
    return meta


def to_timestamp(date_str: str) -> int:
    """YYYY-MM-DD を UTC の UNIX 時刻(秒)にする。Dify の time 型メタデータは timestamp で持つ"""
    d = dt.datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    return int(d.timestamp())


def create_dataset(client: httpx.Client, name: str) -> dict:
    payload = {
        "name": name,
        "description": "社内規程(knowledge 章のサンプル)",
        "indexing_technique": "high_quality",
        "permission": "only_me",
        "embedding_model_provider": EMBEDDING_PROVIDER,
        "embedding_model": EMBEDDING_MODEL,
        "retrieval_model": {
            "search_method": "hybrid_search",
            "reranking_enable": False,
            "reranking_mode": "weighted_score",
            "reranking_model": None,
            "weights": {
                "weight_type": "customized",
                "vector_setting": {
                    "vector_weight": 0.7,
                    "embedding_provider_name": EMBEDDING_PROVIDER,
                    "embedding_model_name": EMBEDDING_MODEL,
                },
                "keyword_setting": {"keyword_weight": 0.3},
            },
            "top_k": 3,
            "score_threshold_enabled": False,
            "score_threshold": None,
        },
    }
    r = client.post("/datasets", json=payload)
    r.raise_for_status()
    return r.json()


def create_metadata_fields(client: httpx.Client, dataset_id: str) -> dict:
    fields = {}
    for name, typ in (("department", "string"), ("effective_date", "time")):
        r = client.post(f"/datasets/{dataset_id}/metadata", json={"type": typ, "name": name})
        r.raise_for_status()
        fields[name] = r.json()["id"]
    return fields


def upload_file(client: httpx.Client, dataset_id: str, path: Path, args: argparse.Namespace) -> dict:
    data = {
        "indexing_technique": "high_quality",
        "doc_form": "text_model",  # General チャンク。Parent-child は hierarchical_model
        "doc_language": "Japanese",
        "process_rule": {
            "mode": "custom",
            "rules": {
                "pre_processing_rules": [
                    {"id": "remove_extra_spaces", "enabled": True},
                    {"id": "remove_urls_emails", "enabled": False},
                ],
                "segmentation": {
                    "separator": args.separator,
                    "max_tokens": args.max_tokens,
                    "chunk_overlap": args.overlap,
                },
            },
        },
    }
    with path.open("rb") as f:
        r = client.post(
            f"/datasets/{dataset_id}/document/create-by-file",
            data={"data": json.dumps(data, ensure_ascii=False)},
            files={"file": (path.name, f, "text/markdown")},
        )
    r.raise_for_status()
    return r.json()


def wait_indexing(client: httpx.Client, dataset_id: str, batch: str, timeout: float = 600.0) -> dict:
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        r = client.get(f"/datasets/{dataset_id}/documents/{batch}/indexing-status")
        r.raise_for_status()
        status = r.json()["data"][0]
        if status["indexing_status"] != last:
            print(f"    {status['indexing_status']}", flush=True)
            last = status["indexing_status"]
        if status["indexing_status"] in ("completed", "error"):
            return status
        time.sleep(2)
    raise TimeoutError(f"indexing did not finish within {timeout}s (batch={batch})")


def set_metadata(client: httpx.Client, dataset_id: str, fields: dict, document_id: str, meta: dict) -> None:
    metadata_list = []
    if "department" in meta:
        metadata_list.append({"id": fields["department"], "name": "department", "value": meta["department"]})
    if "effective_date" in meta:
        metadata_list.append(
            {"id": fields["effective_date"], "name": "effective_date", "value": to_timestamp(meta["effective_date"])}
        )
    payload = {"operation_data": [{"document_id": document_id, "metadata_list": metadata_list, "partial_update": False}]}
    r = client.post(f"/datasets/{dataset_id}/documents/metadata", json=payload)
    r.raise_for_status()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("directory", help="Markdown を置いたディレクトリ")
    parser.add_argument("--name", default="knowledge: policies", help="ナレッジ名(ワークスペース内で一意)")
    parser.add_argument("--separator", default="\\n\\n", help="General チャンクの区切り文字(既定: 空行)")
    parser.add_argument("--max-tokens", type=int, default=500, help="Maximum chunk length(既定: 500)")
    parser.add_argument("--overlap", type=int, default=50, help="Chunk overlap(既定: 50)")
    args = parser.parse_args()
    args.separator = args.separator.replace("\\n", "\n")

    load_dotenv()
    base = os.environ.get("DIFY_API_BASE", "http://localhost/v1")
    api_key = os.environ["DIFY_KNOWLEDGE_API_KEY"]

    files = sorted(Path(args.directory).glob("*.md"))
    if not files:
        print("no markdown files", file=sys.stderr)
        return 1

    with httpx.Client(base_url=base, headers={"Authorization": f"Bearer {api_key}"}, timeout=120.0) as client:
        dataset = create_dataset(client, args.name)
        dataset_id = dataset["id"]
        print(f"dataset: {dataset['name']} ({dataset_id})")

        fields = create_metadata_fields(client, dataset_id)
        print(f"metadata fields: {fields}")

        summary = []
        for path in files:
            meta = parse_frontmatter(path.read_text(encoding="utf-8"))
            print(f"- {path.name}: upload")
            created = upload_file(client, dataset_id, path, args)
            document_id = created["document"]["id"]
            status = wait_indexing(client, dataset_id, created["batch"])
            if status["indexing_status"] == "error":
                print(f"    error: {status['error']}", file=sys.stderr)
                return 1
            set_metadata(client, dataset_id, fields, document_id, meta)
            summary.append((path.name, document_id, status["total_segments"], meta))
            print(f"    chunks={status['total_segments']} metadata={meta}")

    print()
    print(f"DIFY_DATASET_ID={dataset_id}")
    for name, document_id, segments, meta in summary:
        print(f"{name}\t{document_id}\tchunks={segments}\tdepartment={meta.get('department')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
