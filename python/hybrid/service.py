"""Dify の HTTP Request ノードから呼ばれる分類サービス(FastAPI + LangGraph)。

workflow 章の support-triage では Question Classifier ノードが問い合わせを 4 種別に分類していた。
この章では「分類だけを LangGraph のサブグラフに逃がし、回答生成と出力の整形は Dify に残す」構成の
外側の部品としてこのサービスを使う。Dify 側の DSL は dsl/hybrid-workflow.yml。

    POST /classify  {"question": "..."}  ->  {"category": "経費" | "勤怠" | "IT" | "その他", "raw": "..."}

起動: .venv/bin/uvicorn service:app --host 0.0.0.0 --port 8104
検証: Dify 1.17.1、langgraph 1.2.12、langchain-ollama 1.1.0、Ollama qwen2.5:7b
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from fastapi import FastAPI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).with_name(".env"))

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

# support-triage の Question Classifier と同じ 4 クラス。説明文もそのまま流用する
CATEGORIES = {
    "経費": "経費精算、立替、領収書、交通費など、お金の払い戻しに関する問い合わせ",
    "勤怠": "休暇申請、残業、打刻、勤務時間など、勤怠に関する問い合わせ",
    "IT": "PC、アカウント、パスワード、社内システムの不具合など、IT に関する問い合わせ",
    "その他": "上記のいずれにも当てはまらない問い合わせ",
}


class ClassifyState(TypedDict, total=False):
    question: str
    raw: str       # モデルの生出力
    category: str  # 正規化した種別


def classify(state: ClassifyState) -> ClassifyState:
    """LLM に種別名だけを答えさせる。Dify の Question Classifier に当たるノード。"""
    llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0)
    lines = "\n".join(f"- {name}: {desc}" for name, desc in CATEGORIES.items())
    messages = [
        SystemMessage(
            content=(
                "あなたは社内ヘルプデスクの分類担当です。問い合わせを次の種別のどれか 1 つに分類し、"
                f"種別名だけを出力してください。\n{lines}"
            )
        ),
        HumanMessage(content=state["question"]),
    ]
    response = llm.invoke(messages)
    return {"raw": str(response.content)}


def normalize(state: ClassifyState) -> ClassifyState:
    """生出力に種別名が含まれていればそれを採用し、無ければ「その他」に倒す。"""
    raw = state.get("raw", "")
    for name in CATEGORIES:
        if name in raw:
            return {"category": name}
    return {"category": "その他"}


builder = StateGraph(ClassifyState)
builder.add_node("classify", classify)
builder.add_node("normalize", normalize)
builder.add_edge(START, "classify")
builder.add_edge("classify", "normalize")
builder.add_edge("normalize", END)
graph = builder.compile()


class ClassifyIn(BaseModel):
    question: str = Field(description="問い合わせ本文")


class ClassifyOut(BaseModel):
    category: str
    raw: str


app = FastAPI(title="Triage classifier (LangGraph)", version="1.0.0")


@app.post("/classify", response_model=ClassifyOut)
def classify_endpoint(body: ClassifyIn) -> ClassifyOut:
    result = graph.invoke({"question": body.question})
    return ClassifyOut(category=result["category"], raw=result.get("raw", ""))


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": OLLAMA_MODEL}
