#!/bin/bash
# ============================================================
# VM Vault Sync — pulls Oracle VM vault to local Obsidian
# Usage:
#   Once:       bash scripts/sync_vault.sh
#   Watch mode: bash scripts/sync_vault.sh --watch
# ============================================================

VM="ubuntu@92.4.74.176"
KEY="$HOME/.ssh/oracle_ai_employee"
REMOTE="$VM:~/ai-employee/AI_Employee_Vault/"
LOCAL="/home/sumair/Documents/GIAIC/Personal AI Employee Hackathon 0/AI_Employee_Vault/"

sync_once() {
    rsync -az --delete \
      -e "ssh -i $KEY" \
      "$REMOTE" "$LOCAL" \
      --exclude='.obsidian/'
    echo "[$(date '+%H:%M:%S')] Vault synced from VM"
}

if [ "$1" == "--watch" ]; then
    echo "Watching VM vault — syncing every 30 seconds. Ctrl+C to stop."
    while true; do
        sync_once
        sleep 30
    done
else
    sync_once
fi
