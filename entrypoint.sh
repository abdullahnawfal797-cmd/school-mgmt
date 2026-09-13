#!/bin/sh
set -e

# Wait for PostgreSQL when Django is configured to use it. SQLite needs no wait.
python manage.py shell <<'PY'
import time

from django.db import connection
from django.db.utils import OperationalError

if connection.vendor == "postgresql":
    max_attempts = 30
    retry_delay_seconds = 2

    for attempt in range(1, max_attempts + 1):
        try:
            connection.ensure_connection()
            print("PostgreSQL is ready.")
            break
        except OperationalError as exc:
            connection.close()
            if attempt == max_attempts:
                raise RuntimeError(
                    "PostgreSQL did not become ready within the startup timeout."
                ) from exc
            print(
                f"Waiting for PostgreSQL "
                f"({attempt}/{max_attempts}); retrying in {retry_delay_seconds}s..."
            )
            time.sleep(retry_delay_seconds)
else:
    print(f"Database backend is {connection.vendor}; PostgreSQL wait skipped.")
PY

python manage.py migrate --noinput

# Optional one-time superuser password reset.
if [ "${RESET_SUPERUSER_PASSWORD_ON_START:-0}" = "1" ]; then
    python manage.py shell <<'PY'
import os
from django.contrib.auth import get_user_model

username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")

if not password:
    raise RuntimeError("DJANGO_SUPERUSER_PASSWORD is empty.")

User = get_user_model()
user = User.objects.get(username=username)
user.set_password(password)
user.save(update_fields=["password"])
print(f"Password reset successfully for superuser: {username}")
PY
fi
python manage.py collectstatic --noinput

echo "Starting School Management System with Waitress..."
exec waitress-serve --listen="0.0.0.0:${PORT:-8000}" school_mgmt.wsgi:application
