#!/bin/bash
# Library progress across all host queues (refine_queue progress files), every INTERVAL s; tolerant of SSH drops.
# Exits when every queue has written its done file. Usage: library_monitor.sh [INTERVAL_S]
I=${1:-600}
Q="nscc-xdliang3-h100-1:xdliang3-h100-1_g0 nscc-xdliang3-h100-1:xdliang3-h100-1_g1 nscc-xdliang3-a800-7:xdliang3-a800-7_g0 nscc-xdliang3-a800-7:xdliang3-a800-7_g1 nscc-xdliang3-a800:a800_g0 nscc-wangzijun-4090:4090_g0 nscc-wangzijun-4090:4090_g2"
while :; do
  line="$(date '+%H:%M PT')"; all=1
  for q in $Q; do
    h=${q%%:*}; n=${q#*:}
    case $h in *4090) D=/home/wangzijun_p25/zhangshuran/core100_inversion ;; *) D=/workspace/wz/home/wangzijun_p25/zhangshuran/core100_inversion ;; esac
    r=$(ssh -o BatchMode=yes -o ConnectTimeout=40 $h "cd $D/batch1; if [ -e lib3_${n}_done.json ]; then echo DONE; else python3 -c \"import json; p=json.load(open('lib3_${n}_progress.json')); d=p.get('done',[]); print(f\\\"{len(d)}/{p['total']} fail={sum(1 for x in d if x.get('rc') not in (0, None))}\\\")\" 2>/dev/null || echo '?'; fi" 2>/dev/null)
    [ "$r" = DONE ] || all=0
    line="$line | ${n}: ${r:-ssh?}"
  done
  echo "$line"
  [ $all = 1 ] && { echo "all library queues done"; exit 0; }
  sleep $I
done
