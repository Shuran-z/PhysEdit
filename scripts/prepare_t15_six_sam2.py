import shutil
from pathlib import Path
base=Path(__file__).resolve().parents[1]
out=base/'review/qwen35_sam2_six_20261016';out.mkdir(exist_ok=True)
src=(base/'scripts/t15_sam2_diagnostic.py').read_text(encoding='utf-8')
src=src.replace("frame_range=[0,123]","frame_range='per manifest duration and native fps'")
src=src.replace("for sid in ('clip03','clip06'):","jobs=[json.loads(l) for l in (ROOT/'inputs.jsonl').read_text().splitlines() if l.strip()]\nfor job in jobs:\n    sid=job['sample_id']")
src=src.replace("for i in range(124):", "end=round(job['duration_s']*fps)\n    assert hashlib.sha256(video.read_bytes()).hexdigest()==job['sha256']\n    for i in range(end+1):")
src=src.replace("if r['frame'] in (0,49,74,98,117,123):", "if r['frame'] in sorted(set([round(end*x) for x in (0,.4,.6,.8,.95,1)])):")
(out/'track.py').write_text(src,encoding='utf-8');compile(src,'track.py','exec')
shutil.copyfile(base/'review/qwen35_view_ablation_20261016/inputs.jsonl',out/'inputs.jsonl')
print('Prepared six-video tracking manifest')
