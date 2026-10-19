#!/usr/bin/env bash
# Переключение сайта между рабочим режимом и заглушкой «Технические работы».
#
# Использование (из корня проекта или из любой папки):
#   bash conf/maintenance.sh on       # включить заглушку
#   bash conf/maintenance.sh off      # вернуть сайт
#   bash conf/maintenance.sh status   # показать текущий режим
set -euo pipefail

CONF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$CONF_DIR")"
NGINX_CONF="$CONF_DIR/nginx.conf"

usage() {
  cat <<'EOF'
Использование: bash conf/maintenance.sh <команда>

Команды:
  on      включить заглушку «Технические работы»
  off     выключить заглушку, вернуть сайт
  status  показать текущий режим
EOF
}

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    echo "Ошибка: Docker Compose не найден (нужен 'docker compose' или 'docker-compose')." >&2
    exit 1
  fi
}

restart_nginx() {
  echo "Перезапускаю контейнер nginx..."
  (cd "$PROJECT_DIR" && compose restart nginx)
}

case "${1:-}" in
  on)
    cp "$CONF_DIR/nginx.maintenance.conf" "$NGINX_CONF"
    restart_nginx
    echo "Готово: заглушка включена, посетители видят «Технические работы»."
    ;;
  off)
    cp "$CONF_DIR/nginx.working.conf" "$NGINX_CONF"
    restart_nginx
    echo "Готово: заглушка выключена, сайт снова работает."
    ;;
  status)
    if cmp -s "$NGINX_CONF" "$CONF_DIR/nginx.maintenance.conf"; then
      echo "Текущий режим: заглушка включена."
    elif cmp -s "$NGINX_CONF" "$CONF_DIR/nginx.working.conf"; then
      echo "Текущий режим: сайт работает."
    else
      echo "Текущий режим: неизвестно — conf/nginx.conf отличается от обоих шаблонов." >&2
      exit 1
    fi
    ;;
  *)
    usage
    exit 1
    ;;
esac
