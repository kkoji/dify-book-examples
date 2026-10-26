"""会話を続ける、ファイルを送る: files/upload → files[] → 会話の一覧・名前変更・削除。

使い方: python examples/conversation_files.py [path/to/file.txt]  # 省略時は data/policies/expense.md
対象: ファイルアップロードを有効にした Chatbot / Chatflow(無効なアプリでは files は黙って捨てられる)
"""

import json
import sys

from _common import ROOT, make_client

DEFAULT_FILE = ROOT.parent / "data" / "policies" / "expense.md"

USER = "service-api-files"


def main(path: str) -> None:
    with make_client() as dify:
        cfg = dify.parameters()["file_upload"]
        print("file_upload:", json.dumps(cfg, ensure_ascii=False))

        up = dify.upload_file(path, user=USER)  # 201。id をあとで files[] に入れる
        print(f"uploaded: id={up['id']} name={up['name']} size={up['size']} mime={up['mime_type']}")

        # 1 ターン目: ファイル付きで新しい会話を始める(conversation_id は空)
        res = dify.chat("添付ファイルを 1 文で要約してください。", user=USER, files=[dify.file_ref(up, "document")])
        conversation_id = res["conversation_id"]
        print(f"turn1 conversation_id={conversation_id}\n  {res['answer'].strip()}")

        # 2 ターン目: conversation_id を渡して続ける。履歴は Dify 側が持つ
        res = dify.chat("その内容は経費と勤怠のどちらの話ですか。", user=USER, conversation_id=conversation_id)
        print(f"turn2\n  {res['answer'].strip()}")

        # 会話とメッセージの一覧は user 単位。message_files に添付が残る
        msgs = dify.messages(conversation_id, user=USER)
        for m in msgs["data"]:
            print(f"message {m['id'][:8]} query={m['query'][:20]!r} files={[f['filename'] for f in m['message_files']]}")

        print("rename:", dify.rename_conversation(conversation_id, user=USER, name="ファイル添付の確認")["name"])
        convs = dify.conversations(user=USER, limit=5)
        print("conversations:", [(c["id"][:8], c["name"], c["status"]) for c in convs["data"]])

        dify.delete_conversation(conversation_id, user=USER)  # 204
        print("deleted")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(DEFAULT_FILE))
