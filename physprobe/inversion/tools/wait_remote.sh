#!/bin/bash
# Wait until a file exists on a remote host, tolerating SSH drops (the NSCC proxy times out now and then).
# Usage: wait_remote.sh HOST REMOTE_FILE [INTERVAL_S] [-- REPORT_COMMAND...]
# Prints a heartbeat line every 10 polls; when the file appears, runs REPORT_COMMAND on the host (if given) and exits 0.
H=$1; F=$2; I=${3:-60}; shift 3 2>/dev/null; [ "$1" = "--" ] && shift
n=0
while :; do
  r=$(ssh -o BatchMode=yes -o ConnectTimeout=60 -o ServerAliveInterval=30 -o ServerAliveCountMax=4 "$H" "test -e '$F' && echo yes || echo no" 2>/dev/null)
  if [ "$r" = yes ]; then
    echo "$(date) found $F"
    [ $# -gt 0 ] && ssh -o BatchMode=yes -o ConnectTimeout=60 "$H" "$*"
    exit 0
  fi
  n=$((n+1)); [ $((n % 10)) -eq 0 ] && echo "$(date) still waiting (${r:-ssh failed})"
  sleep "$I"
done
