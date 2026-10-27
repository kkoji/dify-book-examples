"""Workflow アプリをテストケースで回し、構造化出力を期待値と比べる評価ランナー。

workflow 章の support-triage Workflow を対象に、testcases.yaml の各ケースを Service API で実行し、
outputs.category(と任意で needs_human)の一致率を出す。--workflow-id を渡すと
POST /v1/workflows/{workflow_id}/run で公開済みの特定バージョンを実行するので、回帰テストに使える。
--judge を付けると、judge: true のケースについて judge.py の LLM-as-a-judge で answer も採点する。

使い方:
    python eval/run_eval.py                                   # 現在の公開版(POST /workflows/run)
    python eval/run_eval.py --workflow-id <公開版の workflow_id>  # 特定バージョン
    python eval/run_eval.py --judge --out result.json

環境変数(.env に書く): DIFY_API_BASE、DIFY_APP_API_KEY(対象 Workflow アプリのキー)
検証: Dify 1.17.1(セルフホスト)、Ollama qwen3:8b、httpx 0.28.1、PyYAML 6.0.2
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx
import yaml
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from judge import judge_answer  # noqa: E402

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_BASE = os.environ.get("DIFY_API_BASE", "http://localhost/v1")
API_KEY = os.environ.get("DIFY_APP_API_KEY")


def run_case(client: httpx.Client, question: str, workflow_id: str | None, user: str) -> dict:
    """1 ケースを blocking で実行し、Service API のレスポンス(JSON)を返す"""
    path = f"/workflows/{workflow_id}/run" if workflow_id else "/workflows/run"
    response = client.post(
        path,
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"inputs": {"question": question}, "response_mode": "blocking", "user": user},
    )
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", default=str(Path(__file__).with_name("testcases.yaml")))
    parser.add_argument("--workflow-id", default=None, help="公開済みバージョンの workflow_id(省略時は現在の公開版)")
    parser.add_argument("--judge", action="store_true", help="judge: true のケースを LLM-as-a-judge でも採点する")
    parser.add_argument("--out", default=None, help="結果 JSON の出力先")
    parser.add_argument("--user", default="eval-runner")
    args = parser.parse_args()

    if not API_KEY:
        sys.exit("DIFY_APP_API_KEY が未設定です。python/.env を確認してください")

    with open(args.cases, encoding="utf-8") as f:
        cases = yaml.safe_load(f)["cases"]

    results = []
    with httpx.Client(base_url=API_BASE, timeout=httpx.Timeout(300.0)) as client:
        for case in cases:
            started = time.time()
            try:
                body = run_case(client, case["question"], args.workflow_id, args.user)
            except httpx.HTTPStatusError as e:
                results.append({"id": case["id"], "ok": False, "error": f"{e.response.status_code} {e.response.text[:200]}"})
                print(f"[ERROR] {case['id']}: {e.response.status_code}")
                continue
            data = body["data"]
            outputs = data.get("outputs") or {}
            expected = case["expected"]
            checks = {"category": outputs.get("category") == expected["category"]}
            if "needs_human" in expected:
                checks["needs_human"] = outputs.get("needs_human") == expected["needs_human"]
            ok = data["status"] == "succeeded" and all(checks.values())
            record = {
                "id": case["id"],
                "ok": ok,
                "status": data["status"],
                "workflow_run_id": body.get("workflow_run_id"),
                "workflow_id": data.get("workflow_id"),
                "expected": expected,
                "actual": {k: outputs.get(k) for k in ("category", "needs_human")},
                "answer": outputs.get("answer"),
                "checks": checks,
                "elapsed_api": round(time.time() - started, 2),
                "elapsed_dify": data.get("elapsed_time"),
                "total_tokens": data.get("total_tokens"),
            }
            if args.judge and case.get("judge"):
                record["judge"] = judge_answer(case["question"], outputs.get("answer", ""), expected["category"])
            results.append(record)
            mark = "PASS" if ok else "FAIL"
            judge_note = f"  judge={record['judge']['score']}" if "judge" in record else ""
            print(f"[{mark}] {case['id']}: category={outputs.get('category')} needs_human={outputs.get('needs_human')}{judge_note}")

    passed = sum(1 for r in results if r.get("ok"))
    summary = {"total": len(results), "passed": passed, "rate": round(passed / len(results), 3) if results else 0.0}
    if args.judge:
        judged = [r["judge"]["score"] for r in results if "judge" in r and r["judge"]["score"] is not None]
        summary["judge_avg"] = round(sum(judged) / len(judged), 2) if judged else None
    print(json.dumps(summary, ensure_ascii=False))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"summary": summary, "results": results}, f, ensure_ascii=False, indent=2)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
