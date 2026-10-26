#!/usr/bin/env bash
# dev でエクスポートした DSL を stg / prod の Dify にインポートする(Dify 1.17.1 で検証)
#
# 使い方:
#   DIFY_CONSOLE_URL=https://stg.example.com/console/api DIFY_EMAIL=... DIFY_PASSWORD=... \
#     ./promote.sh dsl/xxx.yml [上書き先の app_id]
#
#   app_id を省略すると新しいアプリとして作る。指定すると、その Workflow / Chatflow の「下書き」を置き換える。
#   どちらの場合も公開(Publish)は別に必要で、このスクリプトでは行わない(手順を最後に表示する)。
#   FORCE=1 を付けると、DSL バージョン差で pending になったときに confirm して続行する。
#
# 移らないもの(インポート後に stg 側で設定する): モデル / ツールの認証情報、secret 型環境変数の値、
# ナレッジの参照(dataset_ids)、Webhook URL、アプリの API キー。

set -euo pipefail

CONSOLE="${DIFY_CONSOLE_URL:?DIFY_CONSOLE_URL を設定してください}"
DSL_FILE="${1:?DSL ファイルを指定してください}"
TARGET_APP_ID="${2:-}"
FORCE="${FORCE:-0}"
COOKIE="$(mktemp)"
trap 'rm -f "$COOKIE"' EXIT

: "${DIFY_EMAIL:?DIFY_EMAIL を設定してください}"
: "${DIFY_PASSWORD:?DIFY_PASSWORD を設定してください}"

PW_B64="$(printf '%s' "$DIFY_PASSWORD" | base64)"
LOGIN="$(curl -sS -c "$COOKIE" -X POST "$CONSOLE/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$DIFY_EMAIL\",\"password\":\"$PW_B64\",\"remember_me\":true}")"
printf '%s' "$LOGIN" | grep -q '"result": *"success"' || { echo "ログインに失敗しました: $LOGIN" >&2; exit 1; }
CSRF="$(awk '$6=="csrf_token"{print $7}' "$COOKIE")"

api() { # api METHOD PATH [JSON]
  if [ $# -ge 3 ]; then
    curl -sS -b "$COOKIE" -X "$1" "$CONSOLE$2" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" -d "$3"
  else
    curl -sS -b "$COOKIE" -X "$1" "$CONSOLE$2" -H "X-CSRF-Token: $CSRF"
  fi
}

# --- インポート本体 ---
BODY="$(DSL_FILE="$DSL_FILE" TARGET_APP_ID="$TARGET_APP_ID" python3 -c '
import json, os
body = {"mode": "yaml-content", "yaml_content": open(os.environ["DSL_FILE"], encoding="utf-8").read()}
if os.environ["TARGET_APP_ID"]:
    body["app_id"] = os.environ["TARGET_APP_ID"]
print(json.dumps(body, ensure_ascii=False))
')"
RESULT="$(api POST "/apps/imports" "$BODY")"
echo "$RESULT" | python3 -m json.tool

STATUS="$(printf '%s' "$RESULT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')"
IMPORT_ID="$(printf '%s' "$RESULT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"

if [ "$STATUS" = "pending" ]; then
  if [ "$FORCE" = "1" ]; then
    echo "DSL バージョンに差があります。FORCE=1 なので confirm します"
    RESULT="$(api POST "/apps/imports/$IMPORT_ID/confirm")"
    echo "$RESULT" | python3 -m json.tool
    STATUS="$(printf '%s' "$RESULT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')"
  else
    echo "DSL バージョンに差があります(pending)。内容を確認して FORCE=1 で再実行してください(10 分で失効)" >&2
    exit 2
  fi
fi

case "$STATUS" in
  completed|completed-with-warnings) ;;
  *) echo "インポートに失敗しました: $STATUS" >&2; exit 1 ;;
esac

APP_ID="$(printf '%s' "$RESULT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["app_id"])')"

# --- 不足プラグイン ---
echo "--- check-dependencies"
api GET "/apps/imports/$APP_ID/check-dependencies" | python3 -m json.tool

cat <<MSG
--- 次にやること(Console で手作業)
1. アプリ $APP_ID を開き、モデル / ツールの認証情報と secret 型環境変数を stg の値に設定する
2. ナレッジを参照しているなら Knowledge Retrieval ノードで stg のナレッジを選び直す
3. Test Run で動作を確認し、「Publish」→「Publish Update」で公開する(インポートは下書きにしか入らない)
MSG

# --- difyctl 版(サーバ側の envs/core-services/shared.env で OPENAPI_ENABLED=true と ENABLE_OAUTH_BEARER=true が必要) ---
# <!-- VERIFY: 著者が実機で確認(本書の検証環境では両フラグが既定の false のため未検証) -->
#   difyctl auth login --host https://stg.example.com
#   difyctl import studio-app --from-file dsl/xxx.yml [--app-id <stg 側の app_id>]
#   # DSL バージョン差は CLI が自動で confirm し、不足プラグインは stderr に "Missing plugin dependencies" と出る
