#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade heads
echo "Migrations complete."

exec "$@"
