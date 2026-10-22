#!/bin/sh
# Database and photo backups for the production-like stack.
#   backup.sh loop      → one backup now, then every BACKUP_INTERVAL_HOURS (default 24)
#   backup.sh once      → a single backup
#   backup.sh verify F  → restore dump F into a scratch database and count the rows
# Keeps the newest BACKUP_KEEP (default 14) of each kind in /backups.
# A backup only counts as done when the dump is complete and non-empty: files are written
# under a temporary name and renamed at the end, so a failure never looks like a backup.
set -u

DB="${PGDATABASE:-sentinela}"
KEEP="${BACKUP_KEEP:-14}"
INTERVAL_H="${BACKUP_INTERVAL_HOURS:-24}"

wait_for_db() {
  tries=0
  until pg_isready -q -d "$DB"; do
    tries=$((tries + 1))
    if [ "$tries" -ge 60 ]; then
      echo "banco indisponível após 2 minutos" >&2
      return 1
    fi
    sleep 2
  done
}

once() {
  wait_for_db || return 1
  stamp=$(date -u +%Y%m%d-%H%M%S)
  dump="/backups/sentinela-$stamp.dump"
  photos="/backups/fotos-$stamp.tgz"
  if ! pg_dump --format=custom --no-owner --file="$dump.part" "$DB"; then
    rm -f "$dump.part"
    echo "backup FALHOU: pg_dump" >&2
    return 1
  fi
  if [ ! -s "$dump.part" ]; then
    rm -f "$dump.part"
    echo "backup FALHOU: dump vazio" >&2
    return 1
  fi
  mv "$dump.part" "$dump"
  # Photos live in the uploads volume, outside the database.
  if tar -czf "$photos.part" -C /data uploads; then
    mv "$photos.part" "$photos"
  else
    rm -f "$photos.part"
    echo "backup das fotos FALHOU" >&2
    return 1
  fi
  echo "backup ok: $(basename "$dump") ($(du -h "$dump" | cut -f1)), $(basename "$photos")"
  for pattern in 'sentinela-*.dump' 'fotos-*.tgz'; do
    # shellcheck disable=SC2012
    ls -1t /backups/$pattern 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
  done
}

verify() {
  file="$1"
  scratch="restore_check"
  wait_for_db || return 1
  dropdb --if-exists "$scratch"
  createdb "$scratch"
  psql -q -d "$scratch" -c "CREATE EXTENSION IF NOT EXISTS postgis"
  if ! pg_restore --no-owner --exit-on-error --dbname="$scratch" "$file"; then
    echo "restauração FALHOU" >&2
    dropdb --if-exists "$scratch"
    return 1
  fi
  psql -At -d "$scratch" \
    -c "SELECT 'ocorrencias=' || count(*) FROM occurrences" \
    -c "SELECT 'usuarios=' || count(*) FROM users" \
    -c "SELECT 'pontos_sensiveis=' || count(*) FROM sensitive_points" \
    -c "SELECT 'migracao=' || version_num FROM alembic_version"
  dropdb "$scratch"
  echo "restauração ok"
}

case "${1:-loop}" in
  once) once ;;
  verify) verify "$2" ;;
  loop)
    while true; do
      once || echo "nova tentativa no próximo ciclo" >&2
      sleep $((INTERVAL_H * 3600))
    done
    ;;
  *)
    echo "uso: backup.sh [loop|once|verify ARQUIVO]" >&2
    exit 2
    ;;
esac
