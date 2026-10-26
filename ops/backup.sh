#!/usr/bin/env bash
# Dify 1.17.1(Docker Compose)のデータを退避する
#
#   1. 同梱 PostgreSQL を pg_dump で論理バックアップ(コンテナが動いているときだけ)
#   2. docker/volumes ディレクトリを丸ごと tar.gz にする
#
# 使い方:
#   DIFY_DOCKER_DIR=/path/to/dify/docker BACKUP_DIR=/path/to/backups ./backup.sh
#   STOP_CONTAINERS=1 を付けると tar の前に docker compose stop し、終了後に start する
#
# 退避先の構成:
#   $BACKUP_DIR/dify-backup-YYYYmmdd-HHMMSS/
#     postgres.sql.gz   pg_dump の出力(同梱 DB が起動しているとき)
#     volumes.tar.gz    docker/volumes 以下すべて(db/data, app/storage, weaviate, plugin_daemon, redis, sandbox, certbot)
#     manifest.txt      日付、対象ディレクトリ、サイズ
#
# 注意:
#   - 外部 PostgreSQL / S3 / ベクトル DB を使う構成では、それぞれのサービス側のバックアップ機能を使う。
#     このスクリプトが面倒を見るのは docker/volumes にあるものだけ
#   - Linux では volumes 配下が root 所有のことがある。その場合は sudo で実行する
#   - 起動したまま tar すると DB のデータファイルは整合性が保証されない。
#     DB の復元には postgres.sql.gz を使い、volumes.tar.gz は停止して取ったものだけを DB 復元に使う

set -euo pipefail

DIFY_DOCKER_DIR="${DIFY_DOCKER_DIR:-$(pwd)}"
BACKUP_DIR="${BACKUP_DIR:-$(pwd)/backups}"
STOP_CONTAINERS="${STOP_CONTAINERS:-0}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
DEST="${BACKUP_DIR}/dify-backup-${TIMESTAMP}"

if [ ! -f "${DIFY_DOCKER_DIR}/docker-compose.yaml" ]; then
  echo "docker-compose.yaml が見つかりません: ${DIFY_DOCKER_DIR}" >&2
  exit 1
fi
if [ ! -d "${DIFY_DOCKER_DIR}/volumes" ]; then
  echo "volumes ディレクトリが見つかりません: ${DIFY_DOCKER_DIR}/volumes" >&2
  exit 1
fi

mkdir -p "${DEST}"
echo "退避先: ${DEST}"

compose() {
  docker compose --project-directory "${DIFY_DOCKER_DIR}" "$@"
}

# 1. pg_dump(同梱 PostgreSQL が起動しているときだけ)
if compose ps --status running --services 2>/dev/null | grep -qx 'db_postgres'; then
  echo "pg_dump を実行します"
  # 接続情報はコンテナ側の環境変数(POSTGRES_USER / POSTGRES_DB)から取る
  compose exec -T db_postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
    | gzip > "${DEST}/postgres.sql.gz"
else
  echo "db_postgres が起動していないので pg_dump は飛ばします"
fi

# 2. volumes の tar
if [ "${STOP_CONTAINERS}" = "1" ]; then
  echo "コンテナを停止します"
  compose stop
  trap 'echo "コンテナを再開します"; compose start' EXIT
fi

echo "volumes を tar します"
tar -C "${DIFY_DOCKER_DIR}" -czf "${DEST}/volumes.tar.gz" volumes

# 3. manifest
{
  echo "date: ${TIMESTAMP}"
  echo "source: ${DIFY_DOCKER_DIR}/volumes"
  echo "stopped_containers: ${STOP_CONTAINERS}"
  echo "dify_image: $(grep -m1 'image: langgenius/dify-api:' "${DIFY_DOCKER_DIR}/docker-compose.yaml" | sed 's/.*image: //')"
  echo "files:"
  ls -l "${DEST}" | tail -n +2
} > "${DEST}/manifest.txt"

cat "${DEST}/manifest.txt"
echo "完了"
