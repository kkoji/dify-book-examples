"""社内 API のダミー実装(FastAPI)。Dify のカスタムツールとして登録する題材。

エンドポイント:
    GET  /employees/{employee_id}  社員情報照会
    POST /it-requests              IT 機器申請

認証: ヘッダー X-API-Key(環境変数 INTERNAL_API_KEY と一致すること)
起動: uvicorn main:app --port 8102
OpenAPI: python export_openapi.py > openapi.json(servers を Dify から到達できる URL にする)
"""

import os
from datetime import date

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

API_KEY = os.environ.get("INTERNAL_API_KEY", "change-me")

app = FastAPI(
    title="Internal HR/IT API",
    version="1.0.0",
    description="社員情報の照会と IT 機器申請を行う社内 API(サンプル)",
)

# サンプル用の固定データ
EMPLOYEES = {
    "E001": {"employee_id": "E001", "name": "山田 太郎", "department": "営業部", "manager_id": "E100"},
    "E002": {"employee_id": "E002", "name": "佐藤 花子", "department": "開発部", "manager_id": "E200"},
}
REQUESTS: list[dict] = []


# securitySchemes として OpenAPI に出るので、Dify 側ではツールの引数ではなく認証設定として扱える
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(x_api_key: str | None = Depends(api_key_header)) -> None:
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")


class Employee(BaseModel):
    employee_id: str
    name: str
    department: str
    manager_id: str


class ItRequestIn(BaseModel):
    employee_id: str = Field(description="申請者の社員 ID(例: E001)")
    device: str = Field(description="申請する機器(例: ノート PC、モニター)")
    reason: str = Field(description="申請理由")


class ItRequestOut(BaseModel):
    request_id: str
    employee_id: str
    device: str
    status: str
    submitted_on: date


@app.get(
    "/employees/{employee_id}",
    operation_id="get_employee",
    summary="社員情報を照会する",
    description="社員 ID から氏名、所属部署、上長の社員 ID を返す。",
    response_model=Employee,
    dependencies=[Depends(require_api_key)],
)
def get_employee(employee_id: str) -> Employee:
    employee = EMPLOYEES.get(employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="employee not found")
    return Employee(**employee)


@app.post(
    "/it-requests",
    operation_id="create_it_request",
    summary="IT 機器を申請する",
    description="社員 ID、機器名、理由を受け取り、申請を受理して申請 ID を返す。",
    response_model=ItRequestOut,
    dependencies=[Depends(require_api_key)],
)
def create_it_request(body: ItRequestIn) -> ItRequestOut:
    if body.employee_id not in EMPLOYEES:
        raise HTTPException(status_code=404, detail="employee not found")
    request_id = f"REQ-{len(REQUESTS) + 1:04d}"
    record = ItRequestOut(
        request_id=request_id,
        employee_id=body.employee_id,
        device=body.device,
        status="received",
        submitted_on=date.today(),
    )
    REQUESTS.append(record.model_dump())
    return record
