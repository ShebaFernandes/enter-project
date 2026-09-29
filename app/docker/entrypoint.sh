#!/bin/sh
set -eu
case "${1:-web}" in
  web) exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --access-logfile - ;;
  worker) exec python manage.py run_outbox_worker ;;
  *) exec "$@" ;;
esac

