"""Pixel mapping of a generated video: affine (ECC, MOTION_AFFINE) from the condition image (reference frame 4, the image the
model was given) onto the generated video's first frame. Returns scale (ax, ay), offset (bx, by), rotation/shear residual
and the ECC correlation; a mapping is accepted when the correlation is >= 0.6 and the off-diagonal terms are small.
Used by eval_generated.py; standalone: python gen_register.py VIDEO CONDITION_PNG"""
import sys
import cv2
import numpy as np


def first_frame(video):
    cap = cv2.VideoCapture(str(video)); ok, im = cap.read(); cap.release()
    return im if ok else None


def register(cond_png, video, size=(427, 240)):
    ref = cv2.imread(str(cond_png)); gen = first_frame(video)
    if ref is None or gen is None: return dict(ok=False, reason='unreadable')
    H, W = gen.shape[:2]; h0, w0 = ref.shape[:2]
    # work at a common small size; the initial guess is the plain resize (condition image -> video frame)
    r = cv2.cvtColor(cv2.resize(ref, size, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    g = cv2.cvtColor(cv2.resize(gen, size, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    M = np.eye(2, 3, dtype=np.float32)
    try:
        cc, M = cv2.findTransformECC(r, g, M, cv2.MOTION_AFFINE, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), None, 5)
    except cv2.error as e:
        return dict(ok=False, reason='ecc_failed: ' + str(e)[:80])
    # M maps small-ref coords -> small-gen coords; convert to condition-image pixels -> video pixels
    sxr, syr = size[0] / w0, size[1] / h0; sxg, syg = W / size[0], H / size[1]
    ax = M[0, 0] * sxr * sxg; ay = M[1, 1] * syr * syg
    bx = M[0, 2] * sxg; by = M[1, 2] * syg
    shear = float(max(abs(M[0, 1]), abs(M[1, 0])))
    ok = cc >= 0.6 and shear < 0.02
    return dict(ok=bool(ok), corr=float(cc), scale=(float(ax), float(ay)), offset=(float(bx), float(by)), shear=shear,
                video_size=(W, H), condition_size=(w0, h0))


if __name__ == '__main__':
    print(register(sys.argv[2], sys.argv[1]))
