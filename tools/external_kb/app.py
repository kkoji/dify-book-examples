"""Dify の External Knowledge API 契約を満たす最小の検索サーバー(BM25、FastAPI)。

Dify は登録したエンドポイントに POST {endpoint}/retrieval を送る。本文は
    {"knowledge_id": "...", "query": "...", "retrieval_setting": {"top_k": 3, "score_threshold": 0.0},
     "metadata_condition": null}
で、応答は {"records": [{"content", "score", "title", "metadata"}]} を返す。metadata は null ではなく {} にする。

起動:
    uvicorn app:app --host 0.0.0.0 --port 8101

環境変数(.env.example 参照): EXTERNAL_KB_API_KEY、EXTERNAL_KB_DOCS_DIR
検証: Dify 1.17.1(セルフホスト)、fastapi 0.115.6、rank-bm25 0.2.2
"""

import os
import re
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from rank_bm25 import BM25Okapi

API_KEY = os.environ.get("EXTERNAL_KB_API_KEY", "change-me")
DOCS_DIR = Path(os.environ.get("EXTERNAL_KB_DOCS_DIR", Path(__file__).parent / "../../data/policies")).resolve()


class RetrievalSetting(BaseModel):
    top_k: int = 3
    score_threshold: float = 0.0


class RetrievalRequest(BaseModel):
    knowledge_id: str
    query: str
    retrieval_setting: RetrievalSetting = Field(default_factory=RetrievalSetting)
    metadata_condition: dict | None = None


class Record(BaseModel):
    content: str
    score: float
    title: str
    metadata: dict = Field(default_factory=dict)


class RetrievalResponse(BaseModel):
    records: list[Record]


def tokenize(text: str) -> list[str]:
    """形態素解析器を使わず、文字 2-gram で日本語を扱う(本番の RAG では tokenizer を差し替える)"""
    text = re.sub(r"\s+", "", text)
    return [text[i : i + 2] for i in range(len(text) - 1)] or [text]


def load_sections(docs_dir: Path) -> list[dict]:
    """Markdown を ## 見出し単位に分け、フロントマターは落とす"""
    sections = []
    for path in sorted(docs_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if text.startswith("---\n"):
            end = text.find("\n---\n", 4)
            text = text[end + 5 :] if end >= 0 else text
        title = path.stem
        m = re.search(r"^# (.+)$", text, flags=re.M)
        if m:
            title = m.group(1).strip()
        parts = re.split(r"^## ", text, flags=re.M)
        for part in parts[1:]:
            heading, _, body = part.partition("\n")
            content = f"## {heading.strip()}\n{body.strip()}"
            sections.append({"title": title, "heading": heading.strip(), "content": content, "file": path.name})
    return sections


SECTIONS = load_sections(DOCS_DIR)
BM25 = BM25Okapi([tokenize(s["content"]) for s in SECTIONS]) if SECTIONS else None

app = FastAPI(title="external-kb", version="0.1.0")


def check_auth(request: Request) -> None:
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {API_KEY}":
        raise HTTPException(status_code=403, detail="invalid api key")


@app.post("/retrieval", response_model=RetrievalResponse)
def retrieval(req: RetrievalRequest, _: None = Depends(check_auth)) -> RetrievalResponse:
    if BM25 is None or not req.query:
        return RetrievalResponse(records=[])
    scores = BM25.get_scores(tokenize(req.query))
    top = max(float(scores.max()), 1e-9)
    ranked = sorted(range(len(SECTIONS)), key=lambda i: scores[i], reverse=True)
    records = []
    for i in ranked[: req.retrieval_setting.top_k]:
        score = float(scores[i]) / top  # 0〜1 に正規化。Dify 側の Score Threshold と比べられるようにする
        if score < req.retrieval_setting.score_threshold or scores[i] <= 0:
            continue
        s = SECTIONS[i]
        records.append(
            Record(
                content=s["content"],
                score=round(score, 4),
                title=f"{s['title']} / {s['heading']}",
                metadata={"file": s["file"], "knowledge_id": req.knowledge_id},
            )
        )
    return RetrievalResponse(records=records)
