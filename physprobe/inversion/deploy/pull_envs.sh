#!/bin/bash
# Pull the simulation and SAM 3.1 environments to this Mac (deployment cache for the A800 evaluation host).
# Each item is a gzip'd tar stream; a .ok marker is written when an item finished. Re-running skips finished items.
set -u
C=/Users/zhangshuran/data/projects/PhysProbe/.local-research/deploy_cache; cd $C
pull() { # name host tar-args...
  local name=$1 host=$2; shift 2
  [ -f $name.ok ] && { echo "skip $name"; return; }
  local t0=$(date +%s)
  ssh -o BatchMode=yes -o ServerAliveInterval=60 $host "tar $* -cf - | gzip -1" > $name.tar.gz && echo "$(date) $name $(du -h $name.tar.gz | cut -f1) in $(( $(date +%s) - t0 )) s" | tee -a pull.log && touch $name.ok
}
pull genesis_cache   nscc-wangzijun-4090 -C /home/wangzijun_p25/.cache genesis
pull genesis_src     nscc-wangzijun-4090 -C /home/wangzijun_p25/liyuhan --exclude=Genesis/.git Genesis
pull genesis_env     nscc-wangzijun-4090 -C /home/wangzijun_p25/miniconda3/envs genesis
# SAM 3.1 trees from a deployed host, through its sam_* links (the trees keep their own directory names: the environment's
# absolute paths point into them)
S=/workspace/wz/sam/data2/zhangshuran/physedit
pull sam_code        nscc-xdliang3-h100-1 -C $S '$(readlink '$S'/sam_code) $(readlink '$S'/sam_env) $(readlink '$S'/sam_source)'
pull sam_weights     nscc-xdliang3-h100-1 -C $S '$(readlink '$S'/sam_weights)'
pull sam_base_env    nscc-xdliang3-h100-1 -C /workspace/wz/sam/data1/zhangshuran/miniconda3/envs cosmos-predict2
echo ALL_DONE | tee -a pull.log
