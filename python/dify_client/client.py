"""Dify Service API(`/v1`)の薄いクライアント。

- 認証: アプリの API キー(`app-` で始まる)を `Authorization: Bearer` で送る。キーは 1 アプリに紐づき、
  バックエンドからだけ使う(ブラウザやモバイルアプリに埋め込まない)
- `user` は呼び出し側が決めるエンドユーザー識別子。会話・ファイル・run の可視範囲を決める
- 戻り値は Dify の JSON をそのまま dict で返す。streaming 系はイベント dict のジェネレータ

検証: Dify 1.17.1(セルフホスト)、httpx 0.28.1
"""

from __future__ import annotations

import mimetypes
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

from .errors import raise_for_status
from .sse import iter_sse

# blocking は応答まで接続を保つので read を長く取る。streaming は約 10 秒ごとに ping が来るので 60 秒で足りる
DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=600.0, write=30.0, pool=10.0)
DEFAULT_STREAM_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0)


class DifyClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost/v1",
        *,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        stream_timeout: httpx.Timeout = DEFAULT_STREAM_TIMEOUT,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        self._stream_timeout = stream_timeout

    # ---- ライフサイクル -------------------------------------------------
    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "DifyClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ---- 共通 ----------------------------------------------------------
    def _json(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self._client.request(method, path, **kwargs)
        raise_for_status(response)
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def _stream(self, method: str, path: str, **kwargs: Any) -> Iterator[dict]:
        with self._client.stream(method, path, timeout=self._stream_timeout, **kwargs) as response:
            raise_for_status(response)
            yield from iter_sse(response)

    # ---- アプリ情報 ----------------------------------------------------
    def info(self) -> dict:
        """`GET /info`: `name`, `mode`(chat / agent-chat / advanced-chat / workflow / agent / completion)など"""
        return self._json("GET", "/info")

    def parameters(self) -> dict:
        """`GET /parameters`: `user_input_form`(inputs の定義)、`file_upload`、`system_parameters`(上限)など"""
        return self._json("GET", "/parameters")

    def meta(self) -> dict:
        """`GET /meta`: `tool_icons`"""
        return self._json("GET", "/meta")

    # ---- Chatbot / Chatflow / Agent: /chat-messages ---------------------
    @staticmethod
    def _chat_payload(
        query: str, user: str, inputs: dict | None, conversation_id: str, files: list[dict] | None,
        workflow_id: str | None, response_mode: str,
    ) -> dict:
        payload: dict[str, Any] = {
            "inputs": inputs or {},
            "query": query,
            "user": user,
            "conversation_id": conversation_id,  # 空文字なら新規会話
            "response_mode": response_mode,
        }
        if files:
            payload["files"] = files
        if workflow_id:  # Chatflow のみ: 公開済みの特定バージョンを指定
            payload["workflow_id"] = workflow_id
        return payload

    def chat(
        self, query: str, *, user: str, inputs: dict | None = None, conversation_id: str = "",
        files: list[dict] | None = None, workflow_id: str | None = None,
    ) -> dict:
        """blocking で 1 ターン送る。Legacy Agent / 新 Agent は blocking 不可(400 `bad_request`)。

        応答: `answer`, `conversation_id`, `message_id`, `task_id`, `metadata.usage`, `metadata.retriever_resources`
        """
        payload = self._chat_payload(query, user, inputs, conversation_id, files, workflow_id, "blocking")
        return self._json("POST", "/chat-messages", json=payload)

    def chat_stream(
        self, query: str, *, user: str, inputs: dict | None = None, conversation_id: str = "",
        files: list[dict] | None = None, workflow_id: str | None = None,
    ) -> Iterator[dict]:
        """streaming で 1 ターン送り、SSE イベントを dict で順に yield する。"""
        payload = self._chat_payload(query, user, inputs, conversation_id, files, workflow_id, "streaming")
        return self._stream("POST", "/chat-messages", json=payload)

    def stop_chat(self, task_id: str, *, user: str) -> dict:
        """`POST /chat-messages/{task_id}/stop`。元リクエストと同じ `user` でないと何もせず success を返す。"""
        return self._json("POST", f"/chat-messages/{task_id}/stop", json={"user": user})

    # ---- Workflow: /workflows/run --------------------------------------
    @staticmethod
    def _workflow_path(workflow_id: str | None) -> str:
        # 特定の公開済みバージョンを実行するときは /workflows/{workflow_id}/run
        return f"/workflows/{workflow_id}/run" if workflow_id else "/workflows/run"

    def run_workflow(
        self, inputs: dict, *, user: str, files: list[dict] | None = None, workflow_id: str | None = None,
    ) -> dict:
        """blocking で実行する。応答: `workflow_run_id`, `task_id`, `data{status, outputs, error, elapsed_time, ...}`。

        `data.status` は `succeeded` / `failed` / `stopped` のほか、Fail Branch などを通ると `partial-succeeded` になる。
        """
        payload: dict[str, Any] = {"inputs": inputs, "user": user, "response_mode": "blocking"}
        if files:
            payload["files"] = files
        return self._json("POST", self._workflow_path(workflow_id), json=payload)

    def run_workflow_stream(
        self, inputs: dict, *, user: str, files: list[dict] | None = None, workflow_id: str | None = None,
    ) -> Iterator[dict]:
        payload: dict[str, Any] = {"inputs": inputs, "user": user, "response_mode": "streaming"}
        if files:
            payload["files"] = files
        return self._stream("POST", self._workflow_path(workflow_id), json=payload)

    def stop_workflow(self, task_id: str, *, user: str) -> dict:
        """`POST /workflows/tasks/{task_id}/stop`。`user` は必須だが開始時と一致しなくてよい。"""
        return self._json("POST", f"/workflows/tasks/{task_id}/stop", json={"user": user})

    def workflow_events(
        self, workflow_run_id: str, *, user: str, include_state_snapshot: bool = False, continue_on_pause: bool = False,
    ) -> Iterator[dict]:
        """`GET /workflow/{workflow_run_id}/events`: 切断後に SSE を購読し直す(Workflow / Chatflow のみ)。

        `include_state_snapshot=True` で実行済みノードの状態を先頭で再生、
        `continue_on_pause=True` で Human Input の一時停止をまたいで購読し続ける。
        """
        params = {
            "user": user,
            "include_state_snapshot": str(include_state_snapshot).lower(),
            "continue_on_pause": str(continue_on_pause).lower(),
        }
        return self._stream("GET", f"/workflow/{workflow_run_id}/events", params=params)

    def workflow_run(self, workflow_run_id: str) -> dict:
        """`GET /workflows/run/{id}`: 実行の状態と結果。`inputs` は JSON 文字列で返るので呼び出し側でパースする。"""
        return self._json("GET", f"/workflows/run/{workflow_run_id}")

    def workflow_logs(
        self, *, keyword: str | None = None, status: str | None = None, page: int = 1, limit: int = 20,
        created_at__before: str | None = None, created_at__after: str | None = None,
        created_by_end_user_session_id: str | None = None,
    ) -> dict:
        """`GET /workflows/logs`: 実行単位のサマリ(Workflow アプリのみ。Chatflow のキーでは空)。"""
        params = {
            k: v
            for k, v in {
                "keyword": keyword, "status": status, "page": page, "limit": limit,
                "created_at__before": created_at__before, "created_at__after": created_at__after,
                "created_by_end_user_session_id": created_by_end_user_session_id,
            }.items()
            if v is not None
        }
        return self._json("GET", "/workflows/logs", params=params)

    # ---- Text Generator: /completion-messages ---------------------------
    def completion(self, inputs: dict, *, user: str, files: list[dict] | None = None) -> dict:
        payload: dict[str, Any] = {"inputs": inputs, "user": user, "response_mode": "blocking"}
        if files:
            payload["files"] = files
        return self._json("POST", "/completion-messages", json=payload)

    def completion_stream(self, inputs: dict, *, user: str, files: list[dict] | None = None) -> Iterator[dict]:
        payload: dict[str, Any] = {"inputs": inputs, "user": user, "response_mode": "streaming"}
        if files:
            payload["files"] = files
        return self._stream("POST", "/completion-messages", json=payload)

    def stop_completion(self, task_id: str, *, user: str) -> dict:
        return self._json("POST", f"/completion-messages/{task_id}/stop", json={"user": user})

    # ---- ファイル ---------------------------------------------------------
    def upload_file(self, path: str | Path, *, user: str, mime_type: str | None = None) -> dict:
        """`POST /files/upload`(multipart)。201 で `id` などを返す。ファイルは同じ `user` からしか参照できない。

        MIME タイプの無いパートは 415 `unsupported_file_type` になるので、拡張子から推定して必ず付ける。
        """
        path = Path(path)
        mime = mime_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with path.open("rb") as fh:
            response = self._client.post(
                "/files/upload", files={"file": (path.name, fh, mime)}, data={"user": user},
            )
        raise_for_status(response)
        return response.json()

    @staticmethod
    def file_ref(upload: dict, file_type: str = "document") -> dict:
        """`upload_file` の結果を `files[]` の要素(`transfer_method: local_file`)に変換する。"""
        return {"type": file_type, "transfer_method": "local_file", "upload_file_id": upload["id"]}

    # ---- 会話 ------------------------------------------------------------
    def conversations(self, *, user: str, last_id: str | None = None, limit: int = 20, sort_by: str | None = None) -> dict:
        params: dict[str, Any] = {"user": user, "limit": limit}
        if last_id:
            params["last_id"] = last_id
        if sort_by:
            params["sort_by"] = sort_by
        return self._json("GET", "/conversations", params=params)

    def messages(self, conversation_id: str, *, user: str, first_id: str | None = None, limit: int = 20) -> dict:
        params: dict[str, Any] = {"conversation_id": conversation_id, "user": user, "limit": limit}
        if first_id:
            params["first_id"] = first_id
        return self._json("GET", "/messages", params=params)

    def rename_conversation(
        self, conversation_id: str, *, user: str, name: str | None = None, auto_generate: bool = False,
    ) -> dict:
        body: dict[str, Any] = {"user": user, "auto_generate": auto_generate}
        if name is not None:
            body["name"] = name
        return self._json("POST", f"/conversations/{conversation_id}/name", json=body)

    def delete_conversation(self, conversation_id: str, *, user: str) -> None:
        self._json("DELETE", f"/conversations/{conversation_id}", json={"user": user})

    # ---- フィードバック ----------------------------------------------------
    def feedback(self, message_id: str, *, user: str, rating: str | None, content: str | None = None) -> dict:
        """`POST /messages/{id}/feedbacks`。`rating` は `like` / `dislike`、`None` で取り消し。"""
        body: dict[str, Any] = {"rating": rating, "user": user}
        if content is not None:
            body["content"] = content
        return self._json("POST", f"/messages/{message_id}/feedbacks", json=body)

    def app_feedbacks(self, *, page: int = 1, limit: int = 20) -> dict:
        """`GET /app/feedbacks`: アプリ全体のフィードバック(全 `user` 横断)。"""
        return self._json("GET", "/app/feedbacks", params={"page": page, "limit": limit})

    # ---- Human Input ------------------------------------------------------
    def human_input_form(self, form_token: str) -> dict:
        """`GET /form/human_input/{form_token}`: `form_content`, `inputs`, `user_actions`, `expiration_time`"""
        return self._json("GET", f"/form/human_input/{form_token}")

    def submit_human_input(self, form_token: str, *, user: str, action: str, inputs: dict | None = None) -> dict:
        """`POST /form/human_input/{form_token}`。`action` は `user_actions[].id`。フォームは 1 回だけ送れる(2 回目は 412)。"""
        return self._json(
            "POST", f"/form/human_input/{form_token}", json={"user": user, "action": action, "inputs": inputs or {}},
        )
