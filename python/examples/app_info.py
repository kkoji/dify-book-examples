"""入口と認証: GET /info, /parameters, /meta でアプリ種別と入力定義を確かめる。

使い方: python examples/app_info.py
"""

import json

from _common import make_client


def main() -> None:
    with make_client() as dify:
        info = dify.info()
        print(f"name={info['name']} mode={info['mode']}")

        params = dify.parameters()
        # inputs のキー名と型はここに従う。要素は {"<型>": {variable, label, required, ...}} の形
        for item in params["user_input_form"]:
            (kind, spec), = item.items()
            print(f"input: {spec['variable']} ({kind}, required={spec.get('required')})")
        print("file_upload:", json.dumps(params["file_upload"], ensure_ascii=False))
        print("system_parameters:", json.dumps(params["system_parameters"]))

        print("tool_icons:", list(dify.meta().get("tool_icons", {}).keys()))


if __name__ == "__main__":
    main()
