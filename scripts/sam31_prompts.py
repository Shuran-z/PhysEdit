"""Frozen initial scene-box identity prompts; no later reference boxes."""
import math


def point(box, others):
    x0, y0, x1, y1 = box
    cx, cy = (x0+x1)/2, (y0+y1)/2
    candidates = []
    for i in range(1, 20):
        for k in range(1, 20):
            x, y = round(x0+(x1-x0)*i/20), round(y0+(y1-y0)*k/20)
            if not (x0 < x < x1 and y0 < y < y1):
                continue
            if any(a <= x <= c and b <= y <= d for a,b,c,d in others):
                continue
            margin = min(x-x0, x1-x, y-y0, y1-y)
            clearance = min((math.hypot(max(a-x,0,x-c),max(b-y,0,y-d))
                             for a,b,c,d in others), default=margin)
            candidates.append((min(margin,clearance), -math.hypot(x-cx,y-cy), x, y))
    if candidates:
        best=max(candidates)
        return [best[2],best[3]], 'exclusive_initial_box_region'
    return [round(cx),round(cy)], 'initial_box_centre'
