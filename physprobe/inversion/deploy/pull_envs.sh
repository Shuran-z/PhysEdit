#!/bin/bash
# Pull the simulation and SAM 3.1 environments to this Mac (deployment cache for the A800 evaluation host).
# Each item is a gzip'd tar stream; a .ok marker is written when an item finished. Re-running skips finished items.
set -u
C=/Users/zhangshuran/data/projects/gravtrace/.local-research/deploy_cache_a800; cd $C
pull() { # name host tar-args...
  local name=$1 host=$2; shift 2
  [ -f $name.ok ] && { echo "skip $name"; return; }
  local t0=$(date +%s)
  ssh -o BatchMode=yes -o ServerAliveInterval=60 $host "tar $* -cf - | gzip -1" > $name.tar.gz && echo "$(date) $name $(du -h $name.tar.gz | cut -f1) in $(( $(date +%s) - t0 )) s" | tee -a pull.log && touch $name.ok
}
pull genesis_cache   nscc-wangzijun-4090 -C /home/wangzijun_p25/.cache genesis
pull genesis_src     nscc-wangzijun-4090 -C /home/wangzijun_p25/liyuhan --exclude=Genesis/.git Genesis
pull genesis_env     nscc-wangzijun-4090 -C /home/wangzijun_p25/miniconda3/envs genesis
pull sam31_code      nscc-hupanwen -C /data2/zhangshuran/physedit full_chain_smoke_20261012_v2/code full_chain_smoke_20261012_v2/env sam31_official_v1/source
pull sam31_weights   nscc-hupanwen -C /data2/zhangshuran/physedit sam31_official_v1/weights
pull sam31_base_env  nscc-hupanwen -C /data1/zhangshuran/miniconda3/envs cosmos-predict2
echo ALL_DONE | tee -a pull.log
