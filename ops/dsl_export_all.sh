#!/usr/bin/env bash
# ワークスペースの全アプリの DSL をエクスポートして dsl/ に並べ、変更があれば commit する(Dify 1.17.1 で検証)
#
# 使い方:
#   DIFY_CONSOLE_URL=http://localhost/console/api DIFY_EMAIL=... DIFY_PASSWORD=... ./dsl_export_all.sh [出力ディレクトリ]
#   COMMIT=1 を付けると git add と commit まで行う(push はしない)
#   INCLUDE_SECRET=true を付けると secret 型環境変数を平文で出す(通常は使わない。Git に載せない)
#
# 認証は Console API のログイン(メール + パスワード)で行う。Console API は Web コンソールが使う内部 API で、
# バージョン間の互換は保証されない。公式 CLI difyctl を使える環境では末尾の difyctl 版に置き換える。
#
# 出力ファイル名は "<app_id の先頭 8 桁>-<アプリ名を英数字と - に正規化>.yml"。
# アプリ名を変えてもファイルが増えないよう、先頭に app_id を付けている。

set -euo pipefail

CONSOLE="${DIFY_CONSOLE_URL:-http://localhost/console/api}"
OUT_DIR="${1:-dsl}"
INCLUDE_SECRET="${INCLUDE_SECRET:-false}"
COMMIT="${COMMIT:-0}"
COOKIE="$(mktemp)"
trap 'rm -f "$COOKIE"' EXIT

: "${DIFY_EMAIL:?DIFY_EMAIL を設定してください}"
: "${DIFY_PASSWORD:?DIFY_PASSWORD を設定してください}"

# --- ログイン(1.17.1 の /login はパスワードを base64 で受け取る) ---
PW_B64="$(printf '%s' "$DIFY_PASSWORD" | base64)"
LOGIN="$(curl -sS -c "$COOKIE" -X POST "$CONSOLE/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$DIFY_EMAIL\",\"password\":\"$PW_B64\",\"remember_me\":true}")"
if ! printf '%s' "$LOGIN" | grep -q '"result": *"success"'; then
  echo "ログインに失敗しました: $LOGIN" >&2
  exit 1
fi
CSRF="$(awk '$6=="csrf_token"{print $7}' "$COOKIE")"

api() { # api METHOD PATH
  curl -sS -b "$COOKIE" -X "$1" "$CONSOLE$2" -H "X-CSRF-Token: $CSRF"
}

mkdir -p "$OUT_DIR"

# --- アプリ一覧(ページング) ---
page=1
while :; do
  LIST="$(api GET "/apps?page=$page&limit=100")"
  printf '%s' "$LIST" | python3 -c '
import json, sys
d = json.load(sys.stdin)
for a in d["data"]:
    print(a["id"], a["mode"], a["name"])
print("__HAS_MORE__", d.get("has_more", False))
' | while read -r app_id mode name; do
    if [ "$app_id" = "__HAS_MORE__" ]; then
      [ "$mode" = "True" ] && echo "$((page + 1))" > "$COOKIE.next" || rm -f "$COOKIE.next"
      continue
    fi
    slug="$(printf '%s' "$name" | tr -cs 'A-Za-z0-9' '-' | sed 's/^-//; s/-$//' | tr 'A-Z' 'a-z')"
    file="$OUT_DIR/${app_id:0:8}-${slug:-app}.yml"
    api GET "/apps/$app_id/export?include_secret=$INCLUDE_SECRET" \
      | python3 -c 'import json, sys; sys.stdout.write(json.load(sys.stdin)["data"])' > "$file"
    echo "exported: $file ($mode)"
  done
  if [ -f "$COOKIE.next" ]; then page="$(cat "$COOKIE.next")"; rm -f "$COOKIE.next"; else break; fi
done

if [ "$COMMIT" = "1" ]; then
  git add "$OUT_DIR"
  if git diff --cached --quiet; then
    echo "変更なし。commit しません"
  else
    git commit -m "dsl: export $(date +%Y-%m-%d) from $CONSOLE"
  fi
fi

# --- difyctl 版(公式 CLI。サーバの版に合わせたビルドを入れる。1.17.1 用は Releases の difyctl-v1.17.1-<os>-<arch>) ---
# セルフホストでは、サーバ側の envs/core-services/shared.env で OPENAPI_ENABLED=true と ENABLE_OAUTH_BEARER=true に
# してからでないと `difyctl auth login` の OAuth device flow が 404 になる(本書の検証環境では両方とも既定の false のまま
# にしたため、ここから下は未検証)。
# <!-- VERIFY: 著者が実機で確認 -->
#   difyctl auth login --host https://dify.example.com      # http:// は --insecure が要る
#   difyctl get app -o name | while read -r app_id; do
#     difyctl export studio-app "$app_id" --output "dsl/$app_id.yml"
#   done
