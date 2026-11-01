"""Build hash-bound three-view contact windows for human/visual review.

Ranking by recorded depth prioritizes review only; no acceptance or rejection.
"""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--contacts', type=Path, required=True)
    ap.add_argument('--roots', nargs='+', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--limit', type=int, default=12)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    receipts = {}
    for root in args.roots:
        for path in (root / 'receipts').glob('*.json'):
            row = json.loads(path.read_text())
            if row.get('media_complete'):
                receipts[row['sample']] = row
    candidates = []
    for path in (args.contacts / 'results').glob('*.json'):
        row = json.loads(path.read_text())
        peaks = [p for p in row.get('peaks', []) if p['dynamic_pair']]
        if peaks and row['sample'] in receipts:
            candidates.append((max(peaks, key=lambda p: p['penetration_m']), row))
    candidates.sort(key=lambda pair: -pair[0]['penetration_m'])
    results = []
    for peak, row in candidates[:args.limit]:
        sid = row['sample']
        try:
            cameras = []
            for video in receipts[sid]['results']:
                path = Path(video['video'])
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                assert digest == video['sha256'] == row['video_hashes'][video['camera']]
                cap = cv2.VideoCapture(str(path))
                try:
                    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    frames = sorted({0, count - 1, *[max(0, min(count - 1, peak['frame'] + d)) for d in range(-3, 4)]})
                    tiles = []
                    for frame in frames:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
                        ok, pixels = cap.read()
                        if not ok:
                            raise ValueError(f'Cannot decode frame {frame}')
                        pixels = cv2.resize(pixels, (640, 360))
                        cv2.putText(pixels, f"{video['camera']} frame {frame}", (8, 25), cv2.FONT_HERSHEY_SIMPLEX, .7, (255, 255, 255), 2)
                        tiles.append(pixels)
                    while len(tiles) % 3:
                        tiles.append(np.zeros_like(tiles[0]))
                    sheet = np.concatenate([np.concatenate(tiles[i:i+3], axis=1) for i in range(0, len(tiles), 3)])
                    dest = args.out / f"{sid}__{video['camera']}.jpg"
                    assert cv2.imwrite(str(dest), sheet)
                    cameras.append(dict(camera=video['camera'], video=str(path), video_sha256=digest, frames=frames,
                                        sheet=str(dest), sheet_sha256=hashlib.sha256(dest.read_bytes()).hexdigest()))
                finally:
                    cap.release()
            result = dict(sample=sid, peak=peak, cameras=cameras, decision='PENDING_VISUAL_REVIEW', formal_acceptance=False)
        except Exception as exc:
            result = dict(sample=sid, error=str(exc), decision='EVIDENCE_COLLECTION_ERROR', formal_acceptance=False)
        (args.out / f'{sid}.json').write_text(json.dumps(result, indent=2))
        results.append(result)
    (args.out / 'summary.json').write_text(json.dumps(dict(selected=len(results), errors=sum('error' in r for r in results),
        formal_acceptance=False, review_completed=False), indent=2))


if __name__ == '__main__':
    main()
