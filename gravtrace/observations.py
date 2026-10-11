"""Fit current-image corner positions at extrema of a fixed SAM3.1 contour.

Rotating tips mix two foreground faces and partial pixel coverage. Their
position must be measured in 2D, not from one foreground/background colour.
No cross-frame warp, motion, geometry, gravity or residual input.
"""
import cv2
import numpy as np
def largest_mask(mask):
    binary = (np.asarray(mask) > 0).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    if n <= 1:
        return binary
    k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return (labels == k).astype(np.uint8)


def refine_box(bgr, mask, integer_box):
    m = largest_mask(mask)
    h, w = m.shape
    yy, xx = np.nonzero(m)
    box = np.asarray(integer_box, float)
    if not len(xx):
        return box.tolist(), {'status': 'empty_mask_integer_fallback', 'edges': []}
    if [int(xx.min()), int(yy.min()), int(xx.max()+1), int(yy.max()+1)] != list(integer_box):
        raise ValueError('Frozen mask component box mismatch')
    if bgr.dtype != np.uint8 or bgr.shape[:2] != m.shape:
        raise ValueError('Original same-shape uint8 BGR required')
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    contour = max(contours, key=cv2.contourArea)
    polygon = cv2.approxPolyDP(contour, 1., True).reshape(-1, 2).astype(np.float32)
    # All contour corners are measured independently from this frame. The
    # structure tensor rejects single edges and ambiguous low-contrast tips.
    derivative_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)/8
    derivative_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)/8
    dense = contour.reshape(-1, 2).astype(float)
    measured = []
    for seed in polygon:
        # A structure tensor can respond to texture on a curved silhouette.
        # Require an actual two-arm turn on the mask contour before treating
        # that response as a corner. Six pixels support the 7x7 RGB patch.
        index = int(np.argmin(np.sum((dense-seed)**2, axis=1)))
        arms = []
        for direction in (-1, 1):
            j, length, steps = index, 0., 0
            while length < 6 and steps < len(dense)-1:
                nxt = (j+direction) % len(dense)
                length += float(np.linalg.norm(dense[nxt]-dense[j]))
                j, steps = nxt, steps+1
            arms.append(dense[j]-seed)
        norm = np.linalg.norm(arms[0])*np.linalg.norm(arms[1])
        if norm < 1e-9:
            continue
        angle = float(np.degrees(np.arccos(np.clip(arms[0]@arms[1]/norm, -1, 1))))
        if angle > 135:
            continue
        sx, sy = seed
        if sx < 5 or sy < 5 or sx >= w-5 or sy >= h-5:
            continue
        q = cv2.cornerSubPix(gray, seed.reshape(1, 1, 2).copy(), (3, 3), (-1, -1),
                             (cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT, 40, .001)).reshape(2)
        if np.max(abs(q-seed)) > 1.5:
            continue
        # cornerSubPix may return its initial seed when no reliable fixed
        # point exists. That is not a measured half-pixel position. Verify
        # the same RGB patch converges from four quarter-pixel offsets.
        starts = [(.25, 0), (-.25, 0), (0, .25), (0, -.25)]
        converged = [q]
        for delta in starts:
            initial = (seed+np.asarray(delta, np.float32)).reshape(1, 1, 2)
            converged.append(cv2.cornerSubPix(gray, initial.copy(), (3, 3), (-1, -1),
                (cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT, 40, .001)).reshape(2))
        convergence_spread = float(np.max(np.ptp(np.asarray(converged), axis=0)))
        if convergence_spread > .05:
            continue
        x, y = np.rint(q).astype(int)
        gx = derivative_x[y-3:y+4, x-3:x+4].ravel()
        gy = derivative_y[y-3:y+4, x-3:x+4].ravel()
        tensor = np.array([[gx@gx, gx@gy], [gx@gy, gy@gy]])/len(gx)
        eigen = np.linalg.eigvalsh(tensor)
        if eigen[0] < 4 or eigen[0]/max(eigen[1], 1e-9) < .1:
            continue
        measured.append({'seed': seed.tolist(), 'point': (q+.5).tolist(),
                         'tensor_eigenvalues': eigen.tolist(), 'contour_angle_deg': angle, 'initialization_spread_px': convergence_spread})
    result, audits = box.copy(), []
    for edge, (axis, sign) in enumerate([(0, -1), (1, -1), (0, 1), (1, 1)]):
        clipped = box[edge] == (0 if sign < 0 else (w if axis == 0 else h))
        # The measured vertex must be an extremum of the actual neural
        # contour. Nearby interior texture corners never set the box.
        raster_extent = box[edge] if sign < 0 else box[edge]-1
        candidates = [p for p in measured if abs(p['seed'][axis]-raster_extent) <= 1
                      and abs(p['point'][axis]-box[edge]) <= 1.5]
        if clipped:
            candidates = []
        if candidates:
            result[edge] = (min if sign < 0 else max)(p['point'][axis] for p in candidates)
        audits.append({'edge': edge, 'status': 'current_rgb_subpixel' if candidates else 'integer_fallback',
                       'integer': float(box[edge]), 'refined': float(result[edge]), 'candidates': candidates})
    # A partially observed corner set mixes continuous image coordinates
    # with raster extrema and makes shape changes look like translation.
    # Certify all four supports (or exact clipping) together. This decision
    # depends only on this frame's pixels, not the fitted trajectory/error.
    certified = all(a['candidates'] or box[a['edge']] ==
                    (0 if a['edge'] < 2 else (w if a['edge'] == 2 else h))
                    for a in audits)
    if not certified:
        for a in audits:
            a['proposal'] = a['refined']
            a['refined'] = a['integer']
            a['status'] = 'incomplete_four_supports_integer_fallback'
        result = box.copy()
    if result[2] <= result[0] or result[3] <= result[1]:
        raise ValueError('Invalid refined box')
    return result.tolist(), {'status': 'certified_four_current_rgb_supports' if certified else
                            'incomplete_four_supports_integer_fallback', 'edges': audits}
