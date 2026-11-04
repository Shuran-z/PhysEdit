"""Read only the registered original frames around the complete fall path."""
import hashlib,json,subprocess
from pathlib import Path
root=Path('/data2/liyuhan/core100_all100_reference_audit_20261101/T15_C04')
identity=json.loads((root/'IDENTITY.json').read_text());video=Path(identity['video_path'])
assert hashlib.sha256(video.read_bytes()).hexdigest()=='535b2246c82c5d1fa3107c9570365461feefc10161c2941211c15ecbae10fdc3'
dest=Path('/data2/liyuhan/core100_remaining74_admission_20261101/t15_c04_path');dest.mkdir(exist_ok=True)
for start,end in ((36,47),(48,59),(60,71)):
    path=dest/('%d_%d.jpg'%(start,end))
    subprocess.run(['/usr/bin/ffmpeg','-v','error','-threads','1','-hwaccel','none','-i',str(video),'-vf',"select='between(n,%d,%d)',scale=768:-1,tile=3x4"%(start,end),'-frames:v','1','-y',str(path)],check=True)
print(json.dumps(dict(source_sha256=identity['video_sha256'],frames=[[36,47],[48,59],[60,71]],files=[str(p)for p in dest.glob('*.jpg')])))
