from pathlib import Path
import json
base=Path(__file__).resolve().parents[1]
out=base/'review/qwen35_sam2_event_20261016'
src=(base/'scripts/qwen35_localize_diagnostic.py').read_text(encoding='utf-8')
src=src.replace("if stage!='locate' and idx==end:","if stage=='event':")
src=src.replace("b=approval[sid]['bbox_xyxy'];x1,y1,x2,y2=[round(x*512/1000) for x in b]", "b=approval[sid]['boxes_by_frame'][str(idx)];x1,y1,x2,y2=[round(x*512/1000) for x in b]")
src=src.replace("'reason':", "'reason':")
src=src.replace('Boxes are location hints only, NOT evidence of support loss.', 'Red outline boxes come from a first-frame-initialized SAM2 tracker, not an event label. Check the enclosed pixels; boxes can be imperfect. Boxes are location hints only, NOT evidence of support loss.')
src=src.replace('{"support_state":"supported / detached_descending / edge_contact_uncertain / unobservable", "fall":null,', '{"target_at_end":"visible / partially_visible / not_visible / uncertain", "support_state":"supported / detached_descending / edge_contact_uncertain / unobservable", "fall":null,')
(out/'qwen_sam2_event.py').write_text(src,encoding='utf-8')
compile(src,'qwen_sam2_event.py','exec')
# Generated from actual SAM2 tracks after visual audit, not hand-drawn late boxes.
approval={}
for sid in ('clip03','clip06'):
    track=json.loads((out/sid/'tracks.json').read_text())
    boxes={}
    for r in track['frames']:
        x1,y1,x2,y2=r['bbox_xyxy']
        boxes[str(r['frame'])]=[max(0,min(1000,round((x1-430)*5))),max(0,min(1000,round((y1-40)*5))),max(0,min(1000,round((x2-430)*5))),max(0,min(1000,round((y2-40)*5)))]
    approval[sid]=dict(location_confirmed=True,continuity_confirmed=True,boxes_by_frame=boxes,
        audit='assistant inspected frames 0,49,74,98,117,123: target retained; no independent pixel gold; thin upper contour may be missed',source='SAM2 first-frame prompt, no late correction')
(out/'verified_boxes.json').write_text(json.dumps(approval,indent=2))
(out/'inputs.jsonl').write_bytes((base/'review/qwen35_presence_zoom_20261016/inputs.jsonl').read_bytes())
print('Prepared SAM2 outline input; no previous Qwen prose or event verdict passed')
