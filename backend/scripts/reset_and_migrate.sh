#!/bin/bash
# Script to reset database and run migrations from scratch
# This script fixes the tenant_id column issue

set -e  # Exit on error

echo "=================================================="
echo "DokyDoc Database Reset and Migration Script"
echo "=================================================="
echo ""

# Step 1: Stop all containers
echo "[Step 1/6] Stopping all Docker containers..."
docker-compose down

# Step 2: Remove volumes to clean database
echo "[Step 2/6] Removing Docker volumes (this will DELETE ALL DATA)..."
docker-compose down -v

# Step 3: Start only database and redis
echo "[Step 3/6] Starting database and Redis services..."
docker-compose up -d db redis

# Step 4: Wait for database to be ready
echo "[Step 4/6] Waiting for database to be ready..."
sleep 5

# Step 5: Run migrations
echo "[Step 5/6] Running Alembic migrations..."
docker-compose run --rm app alembic upgrade head

# Step 6: Start all services
echo "[Step 6/6] Starting all services..."
docker-compose up -d

echo ""
echo "=================================================="
echo "✅ Database reset and migration completed!"
echo "=================================================="
echo ""
echo "You can now access the application."
echo "Check logs with: docker-compose logs -f"
