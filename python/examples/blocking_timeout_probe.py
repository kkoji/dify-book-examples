"""blocking のタイムアウト実測: 長い Workflow を blocking で呼び、どの層が何秒で切るか(または完走するか)を記録する。

使い方: python examples/blocking_timeout_probe.py
対象: 6 分以上かかる Workflow(検証では loop-refine を loop_count 15 にしたコピーを使った)
"""

import datetime
import time

import httpx
from _common import make_client

from dify_client import DifyAPIError

USER = "service-api-timeout-probe"


def main() -> None:
    print("start", datetime.datetime.now().isoformat())
    t0 = time.monotonic()
    # 既定の read timeout(600 秒)より長く待つ
    with make_client() as dify:
        dify._client.timeout = httpx.Timeout(connect=10.0, read=1800.0, write=30.0, pool=10.0)
        try:
            res = dify.run_workflow({"question": "先週の出張で立て替えたタクシー代はどうやって精算すればいいですか。"}, user=USER)
            data = res["data"]
            print(f"completed after {time.monotonic() - t0:.1f}s: status={data['status']} elapsed_time={data['elapsed_time']:.1f}s steps={data['total_steps']}")
        except DifyAPIError as e:
            print(f"HTTP error after {time.monotonic() - t0:.1f}s: status={e.status} code={e.code} message={e.message}")
        except httpx.HTTPError as e:
            print(f"transport error after {time.monotonic() - t0:.1f}s: {type(e).__name__}: {e}")
    print("end", datetime.datetime.now().isoformat())


if __name__ == "__main__":
    main()
