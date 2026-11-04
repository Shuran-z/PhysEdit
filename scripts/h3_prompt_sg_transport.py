"""Task SSH transport for H3 prompt-version migration; no credential output."""
import subprocess
HOST='yangkaiyuan@172.25.72.115'
KEY='C:/Users/24511/.ssh/id_ed25519_sg88n5'
SSH=['-i',KEY,'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=2']
PY='/data/yangkaiyuan/cogvideox15_attn_ffn_lora_trial_20261030/venv/bin/python'
def run(code,timeout=120,python='python3'):
 p=subprocess.run(['ssh',*SSH,HOST,python+' -'],input=code.encode(),capture_output=True,timeout=timeout)
 if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-3000:])
 return p.stdout.decode()
def copy(local,remote):subprocess.run(['scp',*SSH,str(local),HOST+':'+remote],check=True)
