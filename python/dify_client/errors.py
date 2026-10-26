"""Service API のエラー応答(`{code, message, status}`)を例外に包む。"""

from __future__ import annotations

import httpx


class DifyAPIError(Exception):
    """HTTP 4xx / 5xx をエラー応答の 3 フィールド付きで表す。

    429 は `code` で 2 種類を見分ける:
      - too_many_requests: アプリの同時実行上限。バックオフして再試行する
      - rate_limit_error: Dify Cloud のプラン課金クォータ。再試行しても解消しない
    """

    def __init__(self, status: int, code: str, message: str, response: httpx.Response | None = None):
        super().__init__(f"{status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message
        self.response = response

    @property
    def retryable(self) -> bool:
        return self.code == "too_many_requests" or self.status >= 500

    @classmethod
    def from_response(cls, response: httpx.Response) -> "DifyAPIError":
        try:
            body = response.json()
        except ValueError:
            body = {}
        return cls(
            status=int(body.get("status", response.status_code)),
            code=str(body.get("code", "unknown")),
            message=str(body.get("message", response.text[:200])),
            response=response,
        )


def raise_for_status(response: httpx.Response) -> httpx.Response:
    """`response.raise_for_status()` の代わりに使い、Dify のエラー本文を例外に載せる。"""
    if response.status_code >= 400:
        # streaming 応答では本文を読み切ってから JSON にする
        if not response.is_closed and not hasattr(response, "_content"):
            response.read()
        raise DifyAPIError.from_response(response)
    return response
