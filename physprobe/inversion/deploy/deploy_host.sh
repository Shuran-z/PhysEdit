#!/bin/bash
# Deploy the evaluation stack onto nscc-xdliang3-a800 under /workspace/wz (container-local disk; HOME is full and the
# large shared storage mount is stale on this node). The original absolute layouts are mirrored under /workspace/wz and
# text files get their path prefixes rewritten once (binary files untouched):
#   /home/wangzijun_p25        -> /workspace/wz/home/wangzijun_p25
#   /data_cached/wangzijun_p25 -> /workspace/wz/data_cached/wangzijun_p25
#   /data2/zhangshuran         -> /workspace/wz/sam/data2/zhangshuran
#   /data1/zhangshuran         -> /workspace/wz/sam/data1/zhangshuran
# Usage (on the Mac): [DEPLOY_HOST=alias] deploy_host.sh [item ...]   items: genesis_env genesis_src genesis_cache assets assets_py ours sam31_code
#                     sam31_weights sam31_base_env shims rewrite check     (default: all, in that order)
# rewrite covers only the Genesis env and SAM trees (default REWRITE_TOPS below); author files
# and our configs must keep their original bytes (sha256 checks) and are reached through the preload redirect instead.
# After deploying, the 'ours' scripts still need PY switched to the /workspace interpreter path (run_batch.py, refine_queue.py).
set -euo pipefail
C=/Users/zhangshuran/data/projects/gravtrace/.local-research/deploy_cache_a800
H=${DEPLOY_HOST:-nscc-xdliang3-a800}; R=/workspace/wz   # same layout on every xdliang3 container host
items=${@:-genesis_env genesis_src genesis_cache assets assets_py ours sam31_code sam31_weights sam31_base_env shims rewrite check}
put() { # tarball  target-dir
  echo "$(date) upload $1 -> $2"
  ssh -o BatchMode=yes -o ServerAliveInterval=60 $H "mkdir -p $2"
  ssh -o BatchMode=yes -o ServerAliveInterval=60 $H "tar -xzf - -C $2" < $C/$1.tar.gz
}
for it in $items; do case $it in
  genesis_env)   put genesis_env   $R/home/wangzijun_p25/miniconda3/envs ;;
  genesis_src)   put genesis_src   $R/home/wangzijun_p25/liyuhan ;;
  genesis_cache) put genesis_cache $R/cache ;;
  assets)        put assets        $R ;;            # tar of absolute paths stored relative to / (home/..., data_cached/...)
  assets_py)     put assets_py     $R ;;            # .py sources of every author dir the replays import from (only .pyc were opened)
  ours)          put ours          $R/home/wangzijun_p25/zhangshuran ;;
  sam31_code)    put sam31_code    $R/sam/data2/zhangshuran/physedit ;;
  sam31_weights) put sam31_weights $R/sam/data2/zhangshuran/physedit ;;
  sam31_base_env) put sam31_base_env $R/sam/data1/zhangshuran/miniconda3/envs ;;
  shims)   # path-redirect preload lib, GL bypass, minimal libGL for SAM's opencv, environment files (issue log F9-F11)
    B=$R/home/wangzijun_p25/zhangshuran/core100_inversion/batch2
    ssh -o BatchMode=yes $H "mkdir -p $R/lib/pyshim $R/lib/gl $B"
    ssh -o BatchMode=yes $H "cat > $R/lib/pathredirect.c && gcc -shared -fPIC -O2 -o $R/lib/libpathredirect.so $R/lib/pathredirect.c -ldl" < $C/pathredirect.c
    ssh -o BatchMode=yes $H "cat > $R/lib/pyshim/sitecustomize.py" < $C/sitecustomize.py
    ssh -o BatchMode=yes $H "cat > $B/genesis_env.sh" < $C/genesis_env.sh
    ssh -o BatchMode=yes $H "cat > $B/sam_env.sh" < $C/sam_env.sh
    ssh -o BatchMode=yes $H "cat > $B/mps_on.sh && chmod +x $B/mps_on.sh" < $C/mps_on.sh
    ssh -o BatchMode=yes $H "E=$R/home/wangzijun_p25/miniconda3/envs/genesis/lib; cd $R/lib/gl && cp -p \$E/libGL.so.1.7.0 \$E/libGLX.so.0.0.0 \$E/libGLdispatch.so.0.0.0 . && ln -sf libGL.so.1.7.0 libGL.so.1 && ln -sf libGLX.so.0.0.0 libGLX.so.0 && ln -sf libGLdispatch.so.0.0.0 libGLdispatch.so.0"
    ;;
  rewrite)
    ssh -o BatchMode=yes $H "R=$R python3 - ${REWRITE_TOPS:-home/wangzijun_p25/miniconda3/envs/genesis sam/data1 sam/data2}" <<'PYEOF'
import os, re
R = os.environ['R']
subs = [(re.compile(r'(?<!/workspace/wz)/home/wangzijun_p25'), R + '/home/wangzijun_p25'),
        (re.compile(r'(?<!/workspace/wz)/data_cached/wangzijun_p25'), R + '/data_cached/wangzijun_p25'),
        (re.compile(r'(?<!/workspace/wz/sam)/data2/zhangshuran'), R + '/sam/data2/zhangshuran'),
        (re.compile(r'(?<!/workspace/wz/sam)/data1/zhangshuran'), R + '/sam/data1/zhangshuran')]
TEXT = ('.py', '.json', '.jsonl', '.yaml', '.yml', '.txt', '.cfg', '.pth', '.sh', '.toml', '.ini', '.md', '.csv')
nfile = nlink = 0
import sys
TOPS = sys.argv[1:]
for root, dirs, files in (w for top in TOPS for w in os.walk(os.path.join(R, top))):
    for f in files:
        p = os.path.join(root, f)
        if os.path.islink(p):
            t = os.readlink(p); t2 = t
            for rx, new in subs: t2 = rx.sub(new, t2)
            if t2 != t: os.remove(p); os.symlink(t2, p); nlink += 1
            continue
        if not (f.endswith(TEXT) or f == 'pyvenv.cfg') or os.path.getsize(p) > 50_000_000: continue
        try: s = open(p, encoding='utf-8').read()
        except Exception: continue
        s2 = s
        for rx, new in subs: s2 = rx.sub(new, s2)
        if s2 != s:
            os.chmod(p, os.stat(p).st_mode | 0o200)   # extracted files keep read-only modes
            open(p, 'w', encoding='utf-8').write(s2); nfile += 1
print('rewritten files', nfile, 'symlinks', nlink)
PYEOF
    ;;
  check)
    ssh -o BatchMode=yes $H "cd $R && . $R/home/wangzijun_p25/zhangshuran/core100_inversion/batch2/genesis_env.sh && $R/home/wangzijun_p25/miniconda3/envs/genesis/bin/python -c 'import genesis, torch; print(\"genesis\", genesis.__version__, genesis.__file__, \"torch\", torch.__version__, torch.cuda.is_available())' 2>&1 | tail -2;
      unset LD_PRELOAD; . $R/home/wangzijun_p25/zhangshuran/core100_inversion/batch2/sam_env.sh; PYTHONPATH=$R/sam/data2/zhangshuran/physedit/sam31_official_v1/source $R/sam/data2/zhangshuran/physedit/full_chain_smoke_20261012_v2/env/bin/python -c 'import torch, sam3; print(\"sam3 ok\", torch.__version__, torch.cuda.is_available())' 2>&1 | tail -2; df -h /workspace | tail -1" ;;
esac; done
