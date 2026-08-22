#!/bin/bash
# Backup KNO database and FAISS index
BACKUP_DIR="backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"
cp knowledge.db "$BACKUP_DIR/knowledge_$TIMESTAMP.db"
cp -r data/vector_store "$BACKUP_DIR/vector_store_$TIMESTAMP"
echo "Backup created: $BACKUP_DIR/knowledge_$TIMESTAMP.db"
# Keep only last 7 backups
ls -t "$BACKUP_DIR"/knowledge_*.db | tail -n +8 | xargs -r rm
ls -d "$BACKUP_DIR"/vector_store_* | tail -n +8 | xargs -r rm -rf
