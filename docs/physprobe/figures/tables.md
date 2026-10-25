### Fig. 1 — known-answer accuracy (reference videos)

| parameter | cases with a band | point estimates | median abs error | 90th pct | truth inside band |
|---|---|---|---|---|---|
| gravity g | 96 | 37 | 1.4% | 6.2% | 87/96 |
| friction mu | 86 | 21 | 0.6% | 4.3% | 77/86 |
| initial speed v | 62 | 36 | 1.0% | 4.7% | 57/62 |

### Fig. 2 — result kinds with known truth

| set | parameter | n | point estimate | interval | one-sided bound | unidentifiable | not explained | no observation | point median abs error | truth inside band |
|---|---|---|---|---|---|---|---|---|---|---|
| reference 30 fps | g | 97 | 38% | 36% | 11% | 8% | 6% | 0% | 1.4% | 87/96 |
| reference 30 fps | mu | 87 | 24% | 20% | 28% | 20% | 9% | 0% | 0.6% | 77/86 |
| reference 30 fps | v | 62 | 58% | 19% | 6% | 11% | 5% | 0% | 1.0% | 57/62 |
| synthetic 15 fps, x1.026 warp | g | 97 | 36% | 33% | 10% | 8% | 10% | 2% | 1.2% | 82/93 |
| synthetic 15 fps, x1.026 warp | mu | 87 | 22% | 20% | 26% | 15% | 15% | 2% | 0.9% | 72/82 |
| synthetic 15 fps, x1.026 warp | v | 62 | 53% | 18% | 6% | 11% | 8% | 3% | 0.8% | 53/59 |
| synthetic 10 fps, 16 frames | g | 97 | 20% | 26% | 13% | 33% | 4% | 4% | 1.6% | 85/91 |
| synthetic 10 fps, 16 frames | mu | 87 | 3% | 18% | 30% | 38% | 6% | 5% | 2.1% | 75/81 |
| synthetic 10 fps, 16 frames | v | 62 | 34% | 31% | 8% | 16% | 5% | 6% | 0.4% | 54/56 |
| synthetic 30 fps, 121 frames | g | 97 | 32% | 38% | 10% | 9% | 10% | 0% | 1.9% | 85/96 |
| synthetic 30 fps, 121 frames | mu | 87 | 22% | 21% | 26% | 17% | 14% | 0% | 0.8% | 75/84 |
| synthetic 30 fps, 121 frames | v | 62 | 50% | 27% | 3% | 15% | 5% | 0% | 0.8% | 59/61 |
| synthetic 15 fps + camera pan, compensated | g | 97 | 35% | 33% | 10% | 8% | 11% | 2% | 1.2% | 80/92 |
| synthetic 15 fps + camera pan, compensated | mu | 87 | 22% | 20% | 26% | 15% | 15% | 2% | 0.8% | 72/82 |
| synthetic 15 fps + camera pan, compensated | v | 62 | 53% | 18% | 6% | 11% | 8% | 3% | 0.9% | 52/58 |
| synthetic 15 fps + camera pan, not compensated | g | 97 | 1% | 8% | 5% | 3% | 80% | 2% | 53.0% | 9/53 |
| synthetic 15 fps + camera pan, not compensated | mu | 87 | 6% | 2% | 7% | 2% | 80% | 2% | 52.1% | 9/42 |
| synthetic 15 fps + camera pan, not compensated | v | 62 | 5% | 3% | 8% | 3% | 77% | 3% | 6.2% | 9/42 |

### Fig. 3 (g) — generated videos, result kinds per model

| model | videos | not validated (gated) | validated | point estimate | interval | one-sided bound | unidentifiable | not explained | no observation | prompt inside band |
|---|---|---|---|---|---|---|---|---|---|---|
| cogvideox_i2v | 873 | 108 | 765 | 0% | 4% | 18% | 9% | 56% | 12% | 110/449 |
| cosmos | 873 | 108 | 765 | 0% | 6% | 20% | 6% | 57% | 11% | 65/426 |
| cosmos3_nano | 873 | 90 | 783 | 1% | 5% | 20% | 8% | 62% | 5% | 85/469 |
| dynamicrafter_i2v | 873 | 99 | 774 | 0% | 2% | 6% | 10% | 37% | 45% | 106/217 |
| hunyuan15_i2v | 873 | 90 | 783 | 1% | 5% | 9% | 4% | 80% | 1% | 52/376 |
| ltx_i2v | 873 | 90 | 783 | 0% | 3% | 24% | 11% | 54% | 7% | 110/497 |
| minimax_h3 | 730 | 70 | 660 | 2% | 10% | 7% | 7% | 53% | 20% | 63/307 |
| physalign_wan22_i2v_a14b | 873 | 108 | 765 | 0% | 3% | 13% | 5% | 77% | 1% | 54/383 |
| physrvg_ti2v5b | 873 | 108 | 765 | 0% | 5% | 26% | 10% | 58% | 1% | 110/535 |
| videogpa_ti2v5b | 873 | 90 | 783 | 0% | 2% | 17% | 9% | 40% | 32% | 88/336 |
| wan22_i2v_a14b | 873 | 108 | 765 | 0% | 4% | 10% | 8% | 65% | 14% | 70/337 |
| wan_ti2v5b | 835 | 81 | 754 | 0% | 4% | 24% | 8% | 38% | 26% | 80/396 |

### Fig. 3 (mu) — generated videos, result kinds per model

| model | videos | not validated (gated) | validated | point estimate | interval | one-sided bound | unidentifiable | not explained | no observation | prompt inside band |
|---|---|---|---|---|---|---|---|---|---|---|
| cogvideox_i2v | 783 | 135 | 648 | 1% | 1% | 24% | 11% | 52% | 11% | 100/427 |
| cosmos | 783 | 135 | 648 | 4% | 2% | 19% | 8% | 54% | 13% | 85/378 |
| cosmos3_nano | 783 | 117 | 666 | 2% | 2% | 28% | 7% | 57% | 4% | 105/458 |
| dynamicrafter_i2v | 783 | 126 | 657 | 0% | 2% | 9% | 8% | 32% | 48% | 73/193 |
| hunyuan15_i2v | 783 | 117 | 666 | 1% | 2% | 10% | 6% | 80% | 2% | 55/340 |
| ltx_i2v | 783 | 117 | 666 | 2% | 1% | 28% | 14% | 50% | 5% | 150/480 |
| minimax_h3 | 660 | 93 | 567 | 6% | 5% | 8% | 7% | 52% | 22% | 61/277 |
| physalign_wan22_i2v_a14b | 783 | 135 | 648 | 1% | 0% | 15% | 9% | 74% | 1% | 71/340 |
| physrvg_ti2v5b | 783 | 135 | 648 | 0% | 1% | 36% | 12% | 50% | 1% | 130/519 |
| videogpa_ti2v5b | 783 | 117 | 666 | 1% | 1% | 22% | 10% | 35% | 31% | 103/323 |
| wan22_i2v_a14b | 783 | 135 | 648 | 2% | 1% | 12% | 7% | 64% | 14% | 74/307 |
| wan_ti2v5b | 755 | 107 | 648 | 1% | 2% | 29% | 10% | 33% | 26% | 108/376 |

### Fig. 3 (v) — generated videos, result kinds per model

| model | videos | not validated (gated) | validated | point estimate | interval | one-sided bound | unidentifiable | not explained | no observation | prompt inside band |
|---|---|---|---|---|---|---|---|---|---|---|
| cogvideox_i2v | 558 | 63 | 495 | 0% | 0% | 29% | 8% | 52% | 10% | 60/348 |
| cosmos | 558 | 63 | 495 | 0% | 3% | 25% | 3% | 57% | 12% | 40/315 |
| cosmos3_nano | 558 | 27 | 531 | 2% | 3% | 25% | 5% | 59% | 7% | 56/365 |
| dynamicrafter_i2v | 558 | 72 | 486 | 0% | 1% | 13% | 7% | 34% | 44% | 52/166 |
| hunyuan15_i2v | 558 | 27 | 531 | 0% | 2% | 18% | 3% | 75% | 2% | 23/339 |
| ltx_i2v | 558 | 27 | 531 | 0% | 0% | 38% | 10% | 45% | 7% | 88/386 |
| minimax_h3 | 463 | 21 | 442 | 5% | 2% | 13% | 6% | 52% | 23% | 47/204 |
| physalign_wan22_i2v_a14b | 558 | 63 | 495 | 0% | 0% | 15% | 6% | 77% | 2% | 45/323 |
| physrvg_ti2v5b | 558 | 63 | 495 | 0% | 0% | 42% | 10% | 47% | 1% | 68/426 |
| videogpa_ti2v5b | 558 | 27 | 531 | 0% | 0% | 26% | 4% | 37% | 32% | 48/268 |
| wan22_i2v_a14b | 558 | 63 | 495 | 0% | 1% | 15% | 2% | 66% | 15% | 52/244 |
| wan_ti2v5b | 531 | 24 | 507 | 0% | 0% | 30% | 5% | 38% | 26% | 44/308 |

### Fig. 4 — gravity prompt response

| model | prompt 1.62: median (n) | prompt 3.71: median (n) | prompt 9.81: median (n) |
|---|---|---|---|
| cogvideox_i2v | 1.20 (8) | 0.99 (13) | 1.54 (11) |
| cosmos | 1.38 (9) | 1.69 (20) | 0.74 (15) |
| cosmos3_nano | 2.05 (11) | 1.07 (19) | 0.74 (10) |
| dynamicrafter_i2v | - (0) | 1.67 (5) | 11.58 (4) |
| hunyuan15_i2v | 1.38 (5) | 1.53 (12) | 1.50 (14) |
| ltx_i2v | 1.40 (5) | 1.07 (13) | 0.74 (8) |
| minimax_h3 | 7.33 (13) | 2.08 (22) | 5.00 (23) |
| physalign_wan22_i2v_a14b | 1.39 (7) | 1.37 (8) | 0.74 (7) |
| physrvg_ti2v5b | 1.38 (9) | 1.41 (18) | 1.01 (9) |
| videogpa_ti2v5b | 3.38 (4) | 2.19 (4) | 1.31 (4) |
| wan22_i2v_a14b | 1.39 (5) | 1.00 (16) | 1.19 (6) |
| wan_ti2v5b | 1.38 (7) | 1.68 (14) | 0.74 (7) |
