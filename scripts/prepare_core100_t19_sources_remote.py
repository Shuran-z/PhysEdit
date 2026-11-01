"""Recover existing Isaac media, source inputs, states and visual evidence on p25."""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(selection, out):
    import cv2
    import numpy as np
    out.mkdir(parents=True, exist_ok=True)
    cases = []
    root = Path('/data_cached/wangzijun_p25/isaac_out/Isaac_T16-T19_Dataset/T19')
    for item in selection['cases']:
        cid, video, sid = item['clip_id'], item['video'], item['native_sample_id']
        folder = out/cid
        folder.mkdir(exist_ok=True)
        native = root/sid
        config = json.loads((native/'config.json').read_text())
        expected_config = (item.get('producer') or {}).get('config_sha256')
        if expected_config:
            assert sha(native/'config.json') == expected_config, cid
        source = Path(video['local_source'])
        assert sha(source) == video['sha256'], (cid, 'video identity')
        cap = cv2.VideoCapture(str(source))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = []
        while True:
            ok, image = cap.read()
            if not ok:
                break
            frames.append(image)
        cap.release()
        assert len(frames) == 210 and abs(fps-30) < 1e-6
        # Enough temporal density to inspect fast contact, followed by late endpoints.
        indices = list(range(0, 61, 3))+[75,90,120,150,180,200,209]
        tiles = []
        for i in indices:
            image = cv2.resize(frames[i], (427,240))
            cv2.putText(image, cid+' frame '+str(i), (8,18), cv2.FONT_HERSHEY_SIMPLEX,
                        .5, (255,255,255), 1)
            tiles.append(image)
        while len(tiles)%4:
            tiles.append(np.zeros_like(tiles[0]))
        sheet = np.vstack([np.hstack(tiles[i:i+4]) for i in range(0,len(tiles),4)])
        assert cv2.imwrite(str(folder/'motion_review.jpg'), sheet)
        assert cv2.imwrite(str(folder/'condition.png'), frames[4])
        # Keep the exact selected video bytes, without modifying the producer's files.
        dest = folder/'reference.mp4'
        if not dest.exists():
            dest.write_bytes(source.read_bytes())
        assert sha(dest) == video['sha256']
        (folder/'config.json').write_bytes((native/'config.json').read_bytes())
        extras = {}
        for name in ['qa.json','event_graph.json','delivery.json','request.json']:
            p = native/'metadata'/name
            if p.exists():
                (folder/name).write_bytes(p.read_bytes())
                extras[name] = dict(sha256=sha(p), data=json.loads(p.read_text()))
        attempt = Path(item['boundary_source']['source_output']) if item.get('producer') else None
        own_attempt = Path(item['producer']['source_output']) if item.get('producer') else None
        found = []
        if own_attempt:
            for p in own_attempt.rglob('*'):
                if p.is_file() and p.suffix in ('.json','.gz') and any(x in p.name.lower() for x in ['state','traject','config','qa','event']):
                    found.append(dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)))
                    if any(x in p.name.lower() for x in ['state','traject']):
                        (folder/p.name).write_bytes(p.read_bytes())
        record = dict(clip_id=cid, sample_id=sid, video_sha256=sha(dest),
                      source_video=str(source), reference_video=str(dest), fps=fps,
                      frames=len(frames), width=frames[0].shape[1], height=frames[0].shape[0],
                      condition_frame_index=4, condition_sha256=sha(folder/'condition.png'),
                      condition_pixel_sha256=hashlib.sha256(frames[4].tobytes()).hexdigest(),
                      config_sha256=sha(folder/'config.json'), review_sheet_sha256=sha(folder/'motion_review.jpg'),
                      review_indices=indices, metadata=extras, original_attempt_files=found)
        cases.append(record)
    # Recover all global sample outcomes in the retained C05 context. This can
    # identify the other side of a contact band without another simulation.
    globals_ = []
    for p in root.glob('T19__bg03_neutral_studio__g01_moon__value_*__global_*'):
        qa = p/'metadata/qa.json'
        if not qa.exists():
            continue
        c = json.loads((p/'config.json').read_text()); q = json.loads(qa.read_text())
        globals_.append(dict(sample_id=c['sample_id'],config=c,config_sha256=sha(p/'config.json'),
                             qa=q,qa_sha256=sha(qa),original_folder=str(p)))
    result = dict(cases=cases, global_outcomes=globals_, no_simulation_started=True)
    (out/'source_receipt.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(dict(out=str(out),cases=len(cases),global_outcomes=len(globals_))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    main(json.loads(args.selection.read_text()),args.out)
