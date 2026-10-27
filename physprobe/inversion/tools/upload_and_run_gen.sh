#!/bin/bash
# Upload the staged generated videos + jobs of one host (sam_gen/all/stage_<host>) and start the SAM 3.1 lean tracker there.
# Usage: upload_and_run_gen.sh hupanwen|h100-2
CODE=/Users/zhangshuran/data/projects/PhysProbe/physprobe/inversion
B=/Users/zhangshuran/data/projects/PhysProbe/.local-research/evaluation/core100_inversion_workspace/evaluation
H=$1; ST=$B/sam_gen/all/stage_$H
case $H in
  hupanwen) A=nscc-hupanwen; P=/data2/zhangshuran/physedit/gen_all; T=/data2/zhangshuran/physedit/lean_tools ;;
  h100-2)   A=nscc-xdliang3-h100-2; P=/workspace/wz/sam/data2/zhangshuran/physedit/gen_all; T=/workspace/wz/home/wangzijun_p25/zhangshuran/core100_inversion/deploy ;;
esac
t0=$(date +%s)
ssh -o BatchMode=yes -o ConnectTimeout=60 $A "mkdir -p $P/videos"
for try in 1 2 3; do
  (cd $ST && COPYFILE_DISABLE=1 tar --no-xattrs -chf - videos jobs.jsonl) | ssh -o BatchMode=yes -o ServerAliveInterval=30 $A "tar -xf - -C $P && ls $P/videos | wc -l" && break
  echo "upload attempt $try failed, retrying"; sleep 30
done
echo "$(date) $H upload done in $(( $(date +%s) - t0 )) s"
case $H in
  hupanwen) scp -q -o BatchMode=yes $CODE/server/run_sam_tracker_hupanwen.sh $A:$T/ && ssh -o BatchMode=yes $A "chmod +x $T/run_sam_tracker_hupanwen.sh; rm -f $P/done; (setsid nohup $T/run_sam_tracker_hupanwen.sh $P 3,4,5,6,7 2 > $P/run.log 2>&1 < /dev/null &)" ;;
  h100-2)   ssh -o BatchMode=yes $A "rm -f $P/done; (setsid nohup $T/run_sam_tracker.sh $P 3 0 /workspace/wz/sam/data2/zhangshuran/physedit/gen_s15v/done > $P/run.log 2>&1 < /dev/null &)" ;;
esac
echo "$(date) $H SAM started"
