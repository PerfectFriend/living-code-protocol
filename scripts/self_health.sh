#!/bin/bash
# Hermes self-health + maintenance window. Runs 6x/day via cron (no-agent mode).
# Pauses all other cron jobs during maintenance, then resumes them.
LOG="$HOME/.hermes/logs/self-health.log"
SELF_ID="08675e02fe8e"
S="$HOME/build/android-sdk/platform-tools/sqlite3"
DB="$HOME/.hermes/state.db"
{
echo "=== $(date '+%F %T') self-health run ==="
GW=$(pgrep -f "gateway run" | head -1)
[ -n "$GW" ] && echo "gateway: OK pid=$GW" || echo "gateway: DOWN"
pgrep -f "cron.scheduler" >/dev/null && echo "cron-scheduler: OK" || echo "cron-scheduler: DOWN"
echo "db quick_check: $($S "file:$DB?mode=ro" 'PRAGMA quick_check;' | head -1)"
echo "mem avail MB: $(free -m | awk '/^Mem:/{print $7}') | disk: $(df -h "$HOME" | tail -1 | awk '{print $4" free of "$2}')"
tail -3000 "$HOME/.hermes/logs/gateway.log" | grep -q "polling recovered" && echo "telegram: polling recovered recently" || echo "telegram: no recent recovery in gateway.log"

# --- maintenance window: pause every other active cron job ---
PAUSED=""
for id in $(hermes cron list 2>/dev/null | grep -oE '^  [0-9a-f]{8,12} \[active\]' | awk '{print $1}'); do
  [ "$id" = "$SELF_ID" ] && continue
  hermes cron pause "$id" >/dev/null 2>&1 && PAUSED="$PAUSED $id"
done
echo "paused during maintenance:$PAUSED"

# --- maintenance ---
cutoff=$(($(date +%s) - 7*86400))
$S "file:$DB?mode=ro" "SELECT id FROM sessions WHERE started_at<$cutoff AND COALESCE(pinned,0)=0;" \
  | xargs -r -P 4 -I{} sh -c 'hermes sessions delete --yes "$1" >/dev/null 2>&1' _ {}
echo "sessions >7d left: $($S "file:$DB?mode=ro" "SELECT COUNT(*) FROM sessions WHERE started_at<$cutoff;")"
$S "$DB" "PRAGMA busy_timeout=15000; DELETE FROM state_meta WHERE key LIKE 'gateway.admission.result.%' AND json_extract(value,'$.result.completed')=1; PRAGMA wal_checkpoint(TRUNCATE);" >/dev/null 2>&1 && echo "state_meta admission cache cleaned + WAL checkpointed"
echo "sessions total: $($S "file:$DB?mode=ro" 'SELECT COUNT(*) FROM sessions;') | messages: $($S "file:$DB?mode=ro" 'SELECT COUNT(*) FROM messages;') | db size: $(du -h "$DB" | cut -f1)"

# --- resume paused jobs ---
for id in $PAUSED; do hermes cron resume "$id" >/dev/null 2>&1; done
echo "resumed:$PAUSED"
echo "=== done ==="
} >> "$LOG" 2>&1
