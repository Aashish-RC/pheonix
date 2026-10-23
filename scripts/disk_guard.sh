#!/usr/bin/env bash
# Pheonix disk guard — keeps a GitHub Codespace from running out of disk.
#
# Usage:
#   scripts/disk_guard.sh status            Show free space, Docker usage, biggest folders
#   scripts/disk_guard.sh check             Exit 1 if free space is below MIN_FREE_GB (CI/hook friendly)
#   scripts/disk_guard.sh require <GB>      Exit 1 unless at least <GB> (+ margin) is free; use before big pulls
#   scripts/disk_guard.sh clean             Safe cleanup: dangling Docker data, caches, __pycache__, oversized logs
#   scripts/disk_guard.sh clean --deep      Also remove ALL unused Docker images and package-manager caches
#
# It never deletes Docker volumes (Ollama models, Qdrant, Meilisearch, Mongo data) and never touches git history.
#
# Tunables (environment variables):
#   MIN_FREE_GB   hard floor, default 3
#   WARN_FREE_GB  warning level, default 6
#   LOG_MAX_MB    rotate files in ./data above this size, default 10
#   LOG_KEEP_LINES lines kept when rotating, default 5000

set -u

MIN_FREE_GB="${MIN_FREE_GB:-3}"
WARN_FREE_GB="${WARN_FREE_GB:-6}"
LOG_MAX_MB="${LOG_MAX_MB:-10}"
LOG_KEEP_LINES="${LOG_KEEP_LINES:-5000}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
have() { command -v "$1" >/dev/null 2>&1; }

# Free GiB on the filesystem that holds the repo (this is the one Codespaces limits).
free_gb() { df -P -BG "$ROOT" | awk 'NR==2 {gsub("G","",$4); print $4}'; }
total_gb() { df -P -BG "$ROOT" | awk 'NR==2 {gsub("G","",$2); print $2}'; }

cmd_status() {
  echo "== Disk (filesystem holding $ROOT)"
  df -h "$ROOT" | sed 's/^/   /'
  local free; free="$(free_gb)"
  if   [ "$free" -lt "$MIN_FREE_GB" ];  then echo "   STATUS: CRITICAL (${free}G free, floor ${MIN_FREE_GB}G)"
  elif [ "$free" -lt "$WARN_FREE_GB" ]; then echo "   STATUS: LOW (${free}G free, warn below ${WARN_FREE_GB}G)"
  else echo "   STATUS: OK (${free}G free)"; fi

  if have docker && docker info >/dev/null 2>&1; then
    echo; echo "== Docker usage"; docker system df 2>/dev/null | sed 's/^/   /'
    echo; echo "== Docker volumes (never auto-deleted)"
    docker system df -v 2>/dev/null | awk '/^Local Volumes space usage/{f=1;next} f&&NF{print "   "$0}' | head -15
  else
    echo; echo "== Docker: not running or not installed (skipped)"
  fi

  echo; echo "== Biggest folders in repo and ~/.pheonix"
  du -sh "$ROOT"/* "$HOME/.pheonix" 2>/dev/null | sort -rh | head -8 | sed 's/^/   /'
  [ -d "$ROOT/model-gateway/node_modules" ] && du -sh "$ROOT/model-gateway/node_modules" | sed 's/^/   /'
}

cmd_check() {
  local free; free="$(free_gb)"
  if [ "$free" -lt "$MIN_FREE_GB" ]; then
    echo "DISK GUARD: only ${free}G free (floor ${MIN_FREE_GB}G). Run: scripts/disk_guard.sh clean" >&2
    return 1
  fi
  [ "$free" -lt "$WARN_FREE_GB" ] && echo "DISK GUARD: warning, ${free}G free." >&2
  return 0
}

cmd_require() {
  local need="${1:-}"
  case "$need" in ''|*[!0-9]*) echo "usage: disk_guard.sh require <GB as whole number>" >&2; return 2;; esac
  local free; free="$(free_gb)"
  local want=$(( need + MIN_FREE_GB ))   # keep the floor free AFTER the download
  if [ "$free" -lt "$want" ]; then
    echo "DISK GUARD: need ${need}G + ${MIN_FREE_GB}G margin = ${want}G, only ${free}G free. Run: scripts/disk_guard.sh clean" >&2
    return 1
  fi
  echo "DISK GUARD: ${free}G free, ${want}G required. OK."
}

rotate_logs() {
  local dir="$ROOT/data" f size_mb
  [ -d "$dir" ] || return 0
  for f in "$dir"/*.log "$dir"/*.jsonl; do
    [ -f "$f" ] || continue
    size_mb=$(( $(stat -c %s "$f") / 1048576 ))
    if [ "$size_mb" -ge "$LOG_MAX_MB" ]; then
      tail -n "$LOG_KEEP_LINES" "$f" > "$f.tmp" && mv "$f.tmp" "$f"
      echo "   rotated $(basename "$f") (was ${size_mb}MB, kept last ${LOG_KEEP_LINES} lines)"
    fi
  done
}

cmd_clean() {
  local deep=0; [ "${1:-}" = "--deep" ] && deep=1
  local before; before="$(free_gb)"
  echo "== Cleaning (free before: ${before}G)"

  if have docker && docker info >/dev/null 2>&1; then
    docker builder prune -f >/dev/null 2>&1 && echo "   docker build cache pruned"
    docker image prune -f   >/dev/null 2>&1 && echo "   dangling docker images pruned"
    docker container prune -f >/dev/null 2>&1 && echo "   stopped containers pruned"
    if [ "$deep" -eq 1 ]; then
      docker image prune -a -f >/dev/null 2>&1 && echo "   ALL unused docker images pruned (they re-download on next 'up')"
    fi
  fi

  find "$ROOT" -name __pycache__ -type d -not -path '*/node_modules/*' -prune -exec rm -rf {} + 2>/dev/null
  rm -rf "$ROOT/.pytest_cache" 2>/dev/null
  echo "   python caches removed"

  have pip && pip cache purge >/dev/null 2>&1 && echo "   pip cache purged"
  if [ "$deep" -eq 1 ]; then
    have pnpm && pnpm store prune >/dev/null 2>&1 && echo "   pnpm store pruned"
    have npm  && npm cache clean --force >/dev/null 2>&1 && echo "   npm cache cleaned"
  fi

  rotate_logs

  local after; after="$(free_gb)"
  echo "== Done. Free: ${before}G -> ${after}G"
  echo "   Docker volumes were NOT touched. To free Ollama models: docker compose exec ollama ollama rm <model>"
}

case "${1:-status}" in
  status)  cmd_status ;;
  check)   cmd_check ;;
  require) shift; cmd_require "${1:-}" ;;
  clean)   shift; cmd_clean "${1:-}" ;;
  -h|--help|help) sed -n '2,19p' "$0" ;;
  *) echo "unknown command: $1 (try: status | check | require | clean | help)" >&2; exit 2 ;;
esac
