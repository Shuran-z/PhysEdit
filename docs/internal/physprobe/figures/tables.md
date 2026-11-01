### Fig. 1 — known-answer accuracy (reference videos)

| parameter | cases with a band | point estimates | median abs error | 90th pct | truth inside band |
|---|---|---|---|---|---|
| gravity g | 96 | 36 | 1.4% | 6.1% | 87/96 |
| friction mu | 86 | 20 | 0.5% | 3.6% | 79/86 |
| initial speed v | 62 | 35 | 0.8% | 2.7% | 59/62 |

### Fig. 2 — result kinds with known truth

| set | parameter | n | point estimate | interval | one-sided bound | unidentifiable | not explained | no observation | point median abs error | truth inside band |
|---|---|---|---|---|---|---|---|---|---|---|
| reference 30 fps | g | 97 | 37% | 38% | 10% | 8% | 6% | 0% | 1.4% | 87/96 |
| reference 30 fps | mu | 87 | 23% | 21% | 28% | 20% | 9% | 0% | 0.5% | 79/86 |
| reference 30 fps | v | 62 | 56% | 23% | 6% | 11% | 3% | 0% | 0.8% | 59/62 |
| synthetic 15 fps, x1.026 warp | g | 97 | 33% | 35% | 10% | 8% | 11% | 2% | 1.3% | 81/93 |
| synthetic 15 fps, x1.026 warp | mu | 87 | 22% | 20% | 26% | 15% | 15% | 2% | 0.9% | 72/82 |
| synthetic 15 fps, x1.026 warp | v | 62 | 52% | 21% | 6% | 11% | 6% | 3% | 0.7% | 54/59 |
| synthetic 10 fps, 16 frames | g | 97 | 19% | 27% | 14% | 32% | 4% | 4% | 1.3% | 84/91 |
| synthetic 10 fps, 16 frames | mu | 87 | 5% | 17% | 30% | 38% | 6% | 5% | 2.5% | 75/81 |
| synthetic 10 fps, 16 frames | v | 62 | 34% | 32% | 8% | 16% | 3% | 6% | 0.5% | 55/56 |
| synthetic 30 fps, 121 frames | g | 97 | 30% | 40% | 10% | 9% | 10% | 0% | 1.7% | 84/96 |
| synthetic 30 fps, 121 frames | mu | 87 | 20% | 23% | 26% | 17% | 14% | 0% | 0.8% | 75/84 |
| synthetic 30 fps, 121 frames | v | 62 | 52% | 26% | 3% | 15% | 5% | 0% | 0.5% | 59/61 |
| synthetic 15 fps + camera pan, compensated | g | 97 | 33% | 35% | 10% | 8% | 11% | 2% | 1.3% | 80/92 |
| synthetic 15 fps + camera pan, compensated | mu | 87 | 21% | 21% | 26% | 15% | 15% | 2% | 0.8% | 72/82 |
| synthetic 15 fps + camera pan, compensated | v | 62 | 52% | 21% | 6% | 11% | 6% | 3% | 0.8% | 53/58 |
| synthetic 15 fps + camera pan, not compensated | g | 97 | 0% | 9% | 5% | 3% | 80% | 2% | - | - |
| synthetic 15 fps + camera pan, not compensated | mu | 87 | 6% | 2% | 7% | 2% | 80% | 2% | 61.5% | 9/42 |
| synthetic 15 fps + camera pan, not compensated | v | 62 | 5% | 3% | 8% | 3% | 77% | 3% | 6.2% | 9/42 |

### Fig. 3 (g) — generated videos, result kinds per model

| model | videos | not validated (gated) | validated | point estimate | interval | one-sided bound | unidentifiable | not explained | no observation | prompt inside band |
|---|---|---|---|---|---|---|---|---|---|---|
| cogvideox_i2v | 873 | 117 | 756 | 1% | 3% | 18% | 10% | 56% | 12% | 107/446 |
| cosmos | 873 | 117 | 756 | 3% | 2% | 20% | 6% | 57% | 12% | 57/426 |
| cosmos3_nano | 873 | 90 | 783 | 1% | 4% | 19% | 8% | 62% | 5% | 82/468 |
| dynamicrafter_i2v | 873 | 99 | 774 | 0% | 2% | 6% | 10% | 37% | 45% | 108/218 |
| hunyuan15_i2v | 873 | 90 | 783 | 1% | 3% | 9% | 4% | 81% | 1% | 48/375 |
| ltx_i2v | 873 | 90 | 783 | 2% | 1% | 24% | 11% | 55% | 7% | 105/497 |
| minimax_h3 | 730 | 70 | 660 | 2% | 10% | 7% | 7% | 53% | 20% | 65/308 |
| physalign_wan22_i2v_a14b | 873 | 117 | 756 | 2% | 1% | 13% | 5% | 77% | 1% | 51/383 |
| physrvg_ti2v5b | 873 | 117 | 756 | 2% | 2% | 26% | 10% | 58% | 1% | 101/535 |
| videogpa_ti2v5b | 873 | 90 | 783 | 0% | 2% | 17% | 9% | 41% | 32% | 88/336 |
| wan22_i2v_a14b | 873 | 117 | 756 | 1% | 3% | 10% | 8% | 64% | 14% | 70/336 |
| wan_ti2v5b | 835 | 81 | 754 | 2% | 2% | 24% | 8% | 38% | 26% | 77/396 |

### Fig. 3 (mu) — generated videos, result kinds per model

| model | videos | not validated (gated) | validated | point estimate | interval | one-sided bound | unidentifiable | not explained | no observation | prompt inside band |
|---|---|---|---|---|---|---|---|---|---|---|
| cogvideox_i2v | 783 | 135 | 648 | 0% | 1% | 24% | 11% | 53% | 11% | 101/425 |
| cosmos | 783 | 135 | 648 | 4% | 2% | 19% | 8% | 54% | 13% | 84/378 |
| cosmos3_nano | 783 | 117 | 666 | 2% | 2% | 28% | 7% | 57% | 4% | 105/458 |
| dynamicrafter_i2v | 783 | 126 | 657 | 0% | 2% | 9% | 8% | 32% | 48% | 80/193 |
| hunyuan15_i2v | 783 | 117 | 666 | 1% | 1% | 10% | 6% | 80% | 2% | 55/340 |
| ltx_i2v | 783 | 117 | 666 | 2% | 1% | 28% | 14% | 50% | 5% | 147/480 |
| minimax_h3 | 660 | 93 | 567 | 6% | 5% | 8% | 7% | 52% | 22% | 61/277 |
| physalign_wan22_i2v_a14b | 783 | 135 | 648 | 1% | 0% | 15% | 9% | 74% | 1% | 71/340 |
| physrvg_ti2v5b | 783 | 135 | 648 | 0% | 1% | 36% | 12% | 50% | 1% | 130/519 |
| videogpa_ti2v5b | 783 | 117 | 666 | 1% | 1% | 22% | 10% | 35% | 31% | 103/323 |
| wan22_i2v_a14b | 783 | 135 | 648 | 2% | 1% | 12% | 7% | 64% | 14% | 74/307 |
| wan_ti2v5b | 755 | 107 | 648 | 1% | 2% | 29% | 10% | 33% | 26% | 107/376 |

### Fig. 3 (v) — generated videos, result kinds per model

| model | videos | not validated (gated) | validated | point estimate | interval | one-sided bound | unidentifiable | not explained | no observation | prompt inside band |
|---|---|---|---|---|---|---|---|---|---|---|
| cogvideox_i2v | 558 | 54 | 504 | 0% | 0% | 29% | 8% | 52% | 10% | 60/354 |
| cosmos | 558 | 54 | 504 | 0% | 3% | 24% | 3% | 58% | 12% | 39/318 |
| cosmos3_nano | 558 | 27 | 531 | 2% | 2% | 25% | 5% | 59% | 7% | 56/364 |
| dynamicrafter_i2v | 558 | 54 | 504 | 0% | 2% | 12% | 7% | 35% | 45% | 53/170 |
| hunyuan15_i2v | 558 | 27 | 531 | 0% | 1% | 18% | 3% | 76% | 2% | 22/341 |
| ltx_i2v | 558 | 27 | 531 | 0% | 0% | 37% | 10% | 46% | 7% | 85/386 |
| minimax_h3 | 463 | 21 | 442 | 5% | 2% | 13% | 6% | 53% | 22% | 47/209 |
| physalign_wan22_i2v_a14b | 558 | 54 | 504 | 0% | 0% | 14% | 6% | 77% | 2% | 45/330 |
| physrvg_ti2v5b | 558 | 54 | 504 | 0% | 0% | 41% | 10% | 48% | 1% | 68/435 |
| videogpa_ti2v5b | 558 | 27 | 531 | 0% | 0% | 26% | 4% | 37% | 33% | 45/265 |
| wan22_i2v_a14b | 558 | 54 | 504 | 0% | 1% | 15% | 2% | 67% | 15% | 51/253 |
| wan_ti2v5b | 531 | 24 | 507 | 0% | 0% | 31% | 5% | 37% | 27% | 43/305 |

### Fig. 4 — gravity prompt response

| model | prompt 1.62: median (n) | prompt 3.71: median (n) | prompt 9.81: median (n) |
|---|---|---|---|
| cogvideox_i2v | 1.47 (8) | 0.96 (9) | 1.62 (10) |
| cosmos | 1.47 (9) | 0.99 (16) | 4.89 (13) |
| cosmos3_nano | 2.04 (11) | 1.04 (17) | 0.72 (9) |
| dynamicrafter_i2v | 12.86 (1) | 1.68 (5) | 11.75 (4) |
| hunyuan15_i2v | 1.47 (5) | 1.42 (10) | 6.56 (10) |
| ltx_i2v | 1.46 (5) | 1.11 (13) | 1.38 (6) |
| minimax_h3 | 7.35 (13) | 2.01 (22) | 5.00 (23) |
| physalign_wan22_i2v_a14b | 1.47 (7) | 1.21 (8) | 0.54 (7) |
| physrvg_ti2v5b | 1.46 (9) | 1.25 (18) | 1.08 (9) |
| videogpa_ti2v5b | 3.51 (4) | 2.45 (4) | 1.54 (3) |
| wan22_i2v_a14b | 1.47 (5) | 0.96 (15) | 0.69 (8) |
| wan_ti2v5b | 1.47 (7) | 1.47 (14) | 0.57 (7) |
