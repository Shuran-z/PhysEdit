"""Independent image controls for the subpixel observation policy."""
import unittest
import numpy as np

from gravtrace.observations import refine_box


def rectangle(dx=.2, dy=.3):
    w, h = 80, 64
    edges = [14+dx, 12+dy, 60+dx, 49+dy]
    x, y = np.arange(w), np.arange(h)
    alpha = np.maximum(0, np.minimum(x+1, edges[2])-np.maximum(x, edges[0]))[None, :]
    alpha = alpha*np.maximum(0, np.minimum(y+1, edges[3])-np.maximum(y, edges[1]))[:, None]
    bgr = np.rint(40+alpha[..., None]*np.array([150,120,100])).astype(np.uint8)
    mask = (alpha >= .5).astype(np.uint8)
    yy, xx = np.nonzero(mask)
    integer = [int(xx.min()), int(yy.min()), int(xx.max()+1), int(yy.max()+1)]
    return bgr, mask, integer, edges


class CurrentFrameSubpixel(unittest.TestCase):
    def test_smooth_textured_ellipse_is_not_a_corner_box(self):
        import cv2
        m = np.zeros((90,110), np.uint8)
        cv2.ellipse(m,(55,45),(30,20),23,0,360,1,-1)
        yy,xx=np.nonzero(m)
        integer=[int(xx.min()),int(yy.min()),int(xx.max()+1),int(yy.max()+1)]
        y,x=np.indices(m.shape)
        texture=100+60*((x//2+y//2)%2)
        bgr=np.repeat(np.where(m,texture,40)[...,None],3,axis=2).astype(np.uint8)
        box,audit=refine_box(bgr,m,integer)
        self.assertEqual(box,integer)
        self.assertEqual(audit['status'],'incomplete_four_supports_integer_fallback')

    def test_nonconvergent_initializer_is_not_a_measurement(self):
        from unittest.mock import patch
        bgr,mask,integer,_=rectangle()
        with patch('cv2.cornerSubPix',side_effect=lambda image,initial,*args: initial.copy()):
            box,audit=refine_box(bgr,mask,integer)
        self.assertEqual(box,integer)
        self.assertEqual(audit['status'],'incomplete_four_supports_integer_fallback')

    def test_anti_aliased_translation(self):
        for dx, dy in [(.2,.3),(.7,.8)]:
            bgr, mask, integer, true = rectangle(dx,dy)
            box, audit = refine_box(bgr, mask, integer)
            self.assertEqual(audit['status'], 'certified_four_current_rgb_supports')
            self.assertLess(np.max(abs(np.array(box)-true)), .25)
            self.assertLess(np.max(abs(np.array(box)-true)), np.max(abs(np.array(integer)-true)))

    def test_uncertain_image_preserves_every_integer_edge(self):
        bgr, mask, integer, _ = rectangle()
        bgr[:] = 80
        box, audit = refine_box(bgr, mask, integer)
        self.assertEqual(box, integer)
        self.assertEqual(audit['status'], 'incomplete_four_supports_integer_fallback')

    def test_largest_component_ignores_isolated_pixel(self):
        bgr, mask, integer, _ = rectangle()
        first, _ = refine_box(bgr, mask, integer)
        mask[3,3] = 1
        second, _ = refine_box(bgr, mask, integer)
        self.assertEqual(first, second)

    def test_mask_mismatch_is_reported_instead_of_hiding_frame(self):
        bgr, mask, integer, _ = rectangle()
        integer[0] -= 1
        with self.assertRaisesRegex(ValueError, 'box mismatch'):
            refine_box(bgr, mask, integer)

    def test_clipped_support_keeps_exact_border(self):
        bgr, mask, _, _ = rectangle()
        mask[:, :20] = 0
        mask[12:49, :60] = 1
        bgr[12:49, :60] = [190,160,140]
        box, _ = refine_box(bgr, mask, [0,12,60,49])
        self.assertEqual(box[0], 0.)


if __name__ == '__main__':
    unittest.main()
