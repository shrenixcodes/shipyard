#!/bin/sh
set -e

attempt=0
max_attempts=30
until alembic upgrade head; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge "$max_attempts" ]; then
        echo "database migrations failed after ${max_attempts} attempts" >&2
        exit 1
    fi
    echo "database not ready yet, retrying migrations (${attempt}/${max_attempts})..."
    sleep 2
done

exec "$@"
