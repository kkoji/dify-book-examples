"""簡易 LLM-as-a-judge。回答案が問い合わせに対して妥当かを 1〜5 で採点する。

Dify の外で動く評価用のモデル呼び出しなので、Ollama の API(/api/chat)を直接叩く。
採点モデルは本番で使うモデルと分けるのが普通だが、ここでは検証環境に合わせて qwen3:8b を使う。

環境変数: OLLAMA_BASE(既定 http://localhost:11434)、JUDGE_MODEL(既定 qwen3:8b)
"""

import json
import os

import httpx

OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434")
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "qwen3:8b")

PROMPT = """あなたは社内ヘルプデスクの回答品質を採点する審査員です。
次の問い合わせと回答案を読み、回答案を 1〜5 の整数で採点してください。

採点基準:
5: 問い合わせの種別({category})に合った内容で、日本語として自然、具体的な次の行動が示されている
3: 種別には合っているが、曖昧または一般論にとどまる
1: 種別と無関係、日本語以外が混じる、または問い合わせに答えていない

問い合わせ:
{question}

回答案:
{answer}

JSON だけを出力してください。形式: {{"score": <1-5 の整数>, "reason": "<30 字以内の理由>"}}
"""


def judge_answer(question: str, answer: str, category: str) -> dict:
    """{"score": int | None, "reason": str} を返す。モデル出力が JSON でなければ score は None"""
    body = {
        "model": JUDGE_MODEL,
        "messages": [{"role": "user", "content": PROMPT.format(question=question, answer=answer, category=category)}],
        "format": "json",
        "stream": False,
        "options": {"temperature": 0},
    }
    try:
        response = httpx.post(f"{OLLAMA_BASE}/api/chat", json=body, timeout=120)
        response.raise_for_status()
        content = response.json()["message"]["content"]
        parsed = json.loads(content)
        score = int(parsed.get("score"))
        return {"score": score if 1 <= score <= 5 else None, "reason": str(parsed.get("reason", ""))}
    except Exception as e:  # noqa: BLE001 - 評価の失敗は本体を止めない
        return {"score": None, "reason": f"judge failed: {e}"}


if __name__ == "__main__":
    import sys

    q, a, c = sys.argv[1:4]
    print(json.dumps(judge_answer(q, a, c), ensure_ascii=False))
