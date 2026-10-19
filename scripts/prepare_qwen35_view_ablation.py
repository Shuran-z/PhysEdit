"""Freeze three input views of the same six clips without changing judge prompt."""
from pathlib import Path
import json,shutil,hashlib
R=Path(__file__).resolve().parents[1]
old=R/'review/qwen35_screen_probe_20261016'
out=R/'review/qwen35_view_ablation_20261016';out.mkdir(exist_ok=False)
shutil.copy2(old/'inputs.jsonl',out/'inputs.jsonl')
s=(old/'judge.py').read_text(encoding='utf-8')
s=s.replace("scope='six-video screening development diagnostic; not independent human validation'", "scope='18 calls: six clips x full/crop/both; development only',roi_xyxy=[350,70,710,430],crop_resize=[512,512],view_order=['full','crop','both'],budget_note='same per-view pixel cap; both has more visual tokens'")
s=s.replace("(root/'receipt.json').write_text(json.dumps(receipt,indent=2))", "(root/'receipt.json').write_text(json.dumps(receipt,indent=2))")
s=s.replace("if len(rows)>6:raise ValueError('bounded diagnostic')", "if len(rows)!=6:raise ValueError('six fixed clips required')\n    rows=[dict(row,view=view) for view in ('full','crop','both') for row in rows]")
s=s.replace("record=dict(sample_id=row['sample_id'],video_sha256=row['sha256'])", "record=dict(sample_id=row['sample_id'],view=row['view'],video_sha256=row['sha256'])")
a=s.index("                messages=[");b=s.index("                record['processor_shapes']",a)
s=s[:a]+'''                full=np.stack(frames)
                crop=np.stack([cv2.resize(f[70:430,350:710],(512,512),interpolation=cv2.INTER_CUBIC) for f in frames])
                views=[full] if row['view']=='full' else [crop] if row['view']=='crop' else [full,crop]
                record['view_shapes']=[list(v.shape) for v in views]
                record['view_array_sha256']=[hashlib.sha256(v.tobytes()).hexdigest() for v in views]
                # Identical text, anchors and decoding. Only visual inputs differ.
                record['text_sha256']=hashlib.sha256((PROMPT+anchors).encode()).hexdigest()
                messages=[{'role':'user','content':[{'type':'video','video':str(path)} for v in views]+[{'type':'text','text':PROMPT+anchors}]}]
                text=processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
                metadata=[VideoMetadata(total_num_frames=end-row['start_frame']+1,fps=fps,width=v.shape[2],height=v.shape[1],
                         duration=row['duration_s'],video_backend='opencv_explicit_frames',frames_indices=relative) for v in views]
                inputs=processor(text=[text],videos=views,video_metadata=metadata,do_sample_frames=False,
                                 size={'longest_edge':26*262144,'shortest_edge':4096},return_tensors='pt').to(model.device)
'''+s[b:]
s=s.replace("assert record['video_grid_thw'][0][0]==13 and min(record['video_grid_thw'][0][1:])>=20, 'unexpected processor resolution'", "assert len(record['video_grid_thw'])==len(views) and all(g[0]==13 and min(g[1:])>=20 for g in record['video_grid_thw']), 'unexpected processor resolution'")
s=s.replace("print(row['sample_id'],record['status']", "print(row['view'],row['sample_id'],record['status']")
(out/'judge.py').write_text(s,encoding='utf-8')
shutil.copy2(old/'local_mapping.json',out/'local_mapping.json')
print(out)
