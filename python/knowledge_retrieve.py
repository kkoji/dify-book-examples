"""Knowledge API の POST /datasets/{id}/retrieve で、検索方式を変えながら同じクエリの結果を比べる。

使い方:
    python knowledge_retrieve.py "タクシー代は精算できますか"
    python knowledge_retrieve.py "有給休暇の申請期限" --method hybrid_search --top-k 5
    python knowledge_retrieve.py "パスワードの長さ" --department information-systems   # メタデータで絞る

--method は semantic_search / full_text_search / hybrid_search / all(既定: all)。
hybrid_search は Weighted Score(Rerank モデルなし)で実行する。

環境変数(.env に書く): DIFY_API_BASE、DIFY_KNOWLEDGE_API_KEY、DIFY_DATASET_ID
検証: Dify 1.17.1(セルフホスト)、Ollama nomic-embed-text、httpx 0.28.1
"""

import argparse
import os
import sys

import httpx
from dotenv import load_dotenv

METHODS = ("semantic_search", "full_text_search", "hybrid_search")


def build_retrieval_model(method: str, dataset: dict, top_k: int, score_threshold: float | None, department: str | None) -> dict:
    model = {
        "search_method": method,
        "reranking_enable": False,
        "reranking_mode": "weighted_score",
        "reranking_model": None,
        "weights": {
            "weight_type": "customized",
            "vector_setting": {
                "vector_weight": 0.7,
                "embedding_provider_name": dataset["embedding_model_provider"],
                "embedding_model_name": dataset["embedding_model"],
            },
            "keyword_setting": {"keyword_weight": 0.3},
        },
        "top_k": top_k,
        "score_threshold_enabled": score_threshold is not None,
        "score_threshold": score_threshold,
    }
    if department:
        model["metadata_filtering_conditions"] = {
            "logical_operator": "and",
            "conditions": [{"name": "department", "comparison_operator": "is", "value": department}],
        }
    return model


def retrieve(client: httpx.Client, dataset_id: str, query: str, retrieval_model: dict) -> list[dict]:
    r = client.post(f"/datasets/{dataset_id}/retrieve", json={"query": query, "retrieval_model": retrieval_model})
    r.raise_for_status()
    return r.json()["records"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query", help="検索クエリ(250 文字まで)")
    parser.add_argument("--method", default="all", choices=METHODS + ("all",))
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--score-threshold", type=float, default=None)
    parser.add_argument("--department", default=None, help="メタデータ department で絞る(例: general-affairs)")
    args = parser.parse_args()

    load_dotenv()
    base = os.environ.get("DIFY_API_BASE", "http://localhost/v1")
    api_key = os.environ["DIFY_KNOWLEDGE_API_KEY"]
    dataset_id = os.environ["DIFY_DATASET_ID"]

    with httpx.Client(base_url=base, headers={"Authorization": f"Bearer {api_key}"}, timeout=120.0) as client:
        dataset = client.get(f"/datasets/{dataset_id}").json()
        methods = METHODS if args.method == "all" else (args.method,)
        for method in methods:
            model = build_retrieval_model(method, dataset, args.top_k, args.score_threshold, args.department)
            records = retrieve(client, dataset_id, args.query, model)
            print(f"== {method} ({len(records)} 件)")
            for rec in records:
                seg = rec["segment"]
                score = rec["score"] if rec["score"] is not None else float("nan")
                preview = seg["content"].replace("\n", " ")[:60]
                print(f"  {score:.4f}  {seg['document']['name']}  #{seg['position']}  {preview}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
