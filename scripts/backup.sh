#!/bin/bash
################################################################################
# DokydDoc — Automated Database Backup Script
# Schedule with cron: 0 2 * * * /home/dokydoc/dokydoc/scripts/backup.sh
# (runs every day at 2 AM)
#
# What it backs up:
#   - PostgreSQL database (pg_dump → compressed SQL)
#   - Uploaded files (/app/uploads/)
#
# Storage: local + optionally S3/Backblaze B2
################################################################################

set -e

# ── Config ────────────────────────────────────────────────────────────────────
APP_DIR="/home/dokydoc/dokydoc"
BACKUP_DIR="/backups/dokydoc"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30                      # Keep backups for 30 days

# From .env
source $APP_DIR/backend/.env

# ── Create backup directory ───────────────────────────────────────────────────
mkdir -p $BACKUP_DIR/postgres
mkdir -p $BACKUP_DIR/uploads

echo "[$(date)] Starting backup..."

# ── PostgreSQL backup ─────────────────────────────────────────────────────────
echo "[$(date)] Backing up PostgreSQL..."
docker exec dokydoc_db pg_dump \
    -U $POSTGRES_USER \
    -d $POSTGRES_DB \
    --format=custom \
    --compress=9 \
    > $BACKUP_DIR/postgres/db_$TIMESTAMP.dump

echo "[$(date)] PostgreSQL backup: $BACKUP_DIR/postgres/db_$TIMESTAMP.dump"

# ── Uploads backup ────────────────────────────────────────────────────────────
echo "[$(date)] Backing up uploads..."
tar -czf $BACKUP_DIR/uploads/uploads_$TIMESTAMP.tar.gz \
    -C /var/lib/docker/volumes/backend_uploads_data/_data/ . \
    2>/dev/null || echo "  [warning] Uploads backup skipped (volume path may differ)"

# ── Optional: Sync to S3/Backblaze ───────────────────────────────────────────
# Uncomment and configure if you want off-site backups:
#
# Install: pip install awscli  OR  apt install rclone
#
# AWS S3:
# aws s3 sync $BACKUP_DIR s3://your-bucket/dokydoc-backups/ \
#     --delete \
#     --storage-class STANDARD_IA
#
# Backblaze B2 (cheaper than S3):
# rclone sync $BACKUP_DIR b2:your-bucket/dokydoc-backups/

# ── Cleanup old backups ───────────────────────────────────────────────────────
echo "[$(date)] Cleaning up backups older than $RETENTION_DAYS days..."
find $BACKUP_DIR -type f -mtime +$RETENTION_DAYS -delete

# ── Report ────────────────────────────────────────────────────────────────────
echo "[$(date)] Backup complete!"
echo "  PostgreSQL: $(du -sh $BACKUP_DIR/postgres/db_$TIMESTAMP.dump | cut -f1)"
du -sh $BACKUP_DIR/ | echo "  Total backup size: $(cut -f1)"
