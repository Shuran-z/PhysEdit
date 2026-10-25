### Fig. 1 — known-answer accuracy (reference videos)

| parameter | cases with a band | point estimates | median abs error | 90th pct | truth inside band |
|---|---|---|---|---|---|
| gravity g | 96 | 35 | 1.4% | 6.2% | 85/96 |
| friction mu | 85 | 20 | 0.7% | 6.2% | 75/85 |
| initial speed v | 62 | 35 | 1.0% | 4.4% | 56/62 |

### Fig. 2 — result kinds with known truth

| set | parameter | n | point estimate | interval | one-sided bound | unidentifiable | not explained | no observation | point median abs error | truth inside band |
|---|---|---|---|---|---|---|---|---|---|---|
| reference 30 fps | g | 97 | 36% | 37% | 11% | 8% | 7% | 0% | 1.4% | 85/96 |
| reference 30 fps | mu | 87 | 23% | 17% | 28% | 21% | 10% | 1% | 0.7% | 75/85 |
| reference 30 fps | v | 62 | 56% | 19% | 6% | 11% | 6% | 0% | 1.0% | 56/62 |
| synthetic 15 fps, x1.026 warp | g | 97 | 35% | 32% | 10% | 8% | 12% | 2% | 1.2% | 80/93 |
| synthetic 15 fps, x1.026 warp | mu | 87 | 22% | 18% | 25% | 15% | 16% | 3% | 0.9% | 70/81 |
| synthetic 15 fps, x1.026 warp | v | 62 | 53% | 16% | 6% | 11% | 10% | 3% | 0.8% | 52/59 |
| synthetic 10 fps, 16 frames | g | 97 | 20% | 23% | 14% | 32% | 7% | 4% | 1.6% | 80/91 |
| synthetic 10 fps, 16 frames | mu | 87 | 3% | 15% | 31% | 34% | 11% | 5% | 2.1% | 70/81 |
| synthetic 10 fps, 16 frames | v | 62 | 31% | 31% | 8% | 16% | 8% | 6% | 0.4% | 52/56 |
| synthetic 30 fps, 121 frames | g | 97 | 30% | 39% | 10% | 9% | 11% | 0% | 1.9% | 83/96 |
| synthetic 30 fps, 121 frames | mu | 87 | 21% | 18% | 26% | 18% | 15% | 1% | 1.0% | 73/83 |
| synthetic 30 fps, 121 frames | v | 62 | 50% | 26% | 3% | 15% | 6% | 0% | 0.8% | 58/61 |
| synthetic 15 fps + camera pan, compensated | g | 97 | 34% | 32% | 10% | 8% | 13% | 2% | 1.2% | 78/92 |
| synthetic 15 fps + camera pan, compensated | mu | 87 | 22% | 18% | 25% | 15% | 16% | 3% | 0.8% | 70/81 |
| synthetic 15 fps + camera pan, compensated | v | 62 | 53% | 16% | 6% | 11% | 10% | 3% | 0.9% | 51/58 |
| synthetic 15 fps + camera pan, not compensated | g | 97 | 1% | 8% | 5% | 3% | 80% | 2% | 53.0% | 9/53 |
| synthetic 15 fps + camera pan, not compensated | mu | 87 | 6% | 2% | 7% | 2% | 80% | 2% | 52.1% | 9/42 |
| synthetic 15 fps + camera pan, not compensated | v | 62 | 5% | 3% | 8% | 3% | 77% | 3% | 6.2% | 9/42 |

### Fig. 3 (g) — generated videos, result kinds per model

| model | videos | not validated (gated) | validated | point estimate | interval | one-sided bound | unidentifiable | not explained | no observation | prompt inside band |
|---|---|---|---|---|---|---|---|---|---|---|
| cogvideox_i2v | 873 | 126 | 747 | 0% | 4% | 18% | 10% | 55% | 12% | 108/433 |
| cosmos | 873 | 126 | 747 | 0% | 6% | 20% | 6% | 56% | 11% | 65/410 |
| cosmos3_nano | 873 | 99 | 774 | 1% | 5% | 20% | 8% | 62% | 5% | 85/460 |
| dynamicrafter_i2v | 873 | 135 | 738 | 0% | 2% | 6% | 11% | 38% | 43% | 105/214 |
| hunyuan15_i2v | 873 | 99 | 774 | 1% | 5% | 9% | 4% | 80% | 1% | 52/369 |
| ltx_i2v | 873 | 99 | 774 | 0% | 3% | 24% | 11% | 54% | 7% | 109/488 |
| minimax_h3 | 730 | 78 | 652 | 2% | 10% | 8% | 8% | 53% | 20% | 63/299 |
| physalign_wan22_i2v_a14b | 873 | 126 | 747 | 0% | 3% | 13% | 5% | 77% | 1% | 54/367 |
| physrvg_ti2v5b | 873 | 126 | 747 | 0% | 5% | 27% | 10% | 58% | 1% | 107/517 |
| videogpa_ti2v5b | 873 | 99 | 774 | 0% | 2% | 18% | 8% | 40% | 32% | 78/330 |
| wan22_i2v_a14b | 873 | 126 | 747 | 0% | 4% | 10% | 8% | 64% | 14% | 70/320 |
| wan_ti2v5b | 835 | 90 | 745 | 0% | 3% | 25% | 8% | 37% | 27% | 76/389 |

### Fig. 3 (mu) — generated videos, result kinds per model

| model | videos | not validated (gated) | validated | point estimate | interval | one-sided bound | unidentifiable | not explained | no observation | prompt inside band |
|---|---|---|---|---|---|---|---|---|---|---|
| cogvideox_i2v | 783 | 153 | 630 | 0% | 0% | 23% | 12% | 54% | 11% | 95/409 |
| cosmos | 783 | 153 | 630 | 2% | 2% | 18% | 10% | 55% | 13% | 85/362 |
| cosmos3_nano | 783 | 135 | 648 | 2% | 0% | 27% | 8% | 57% | 4% | 105/443 |
| dynamicrafter_i2v | 783 | 180 | 603 | 0% | 1% | 11% | 8% | 32% | 48% | 70/173 |
| hunyuan15_i2v | 783 | 135 | 648 | 1% | 1% | 10% | 6% | 81% | 1% | 49/324 |
| ltx_i2v | 783 | 135 | 648 | 1% | 0% | 29% | 15% | 50% | 5% | 147/463 |
| minimax_h3 | 660 | 108 | 552 | 6% | 4% | 9% | 8% | 52% | 21% | 60/267 |
| physalign_wan22_i2v_a14b | 783 | 153 | 630 | 0% | 0% | 14% | 9% | 76% | 1% | 62/326 |
| physrvg_ti2v5b | 783 | 153 | 630 | 0% | 0% | 34% | 13% | 52% | 1% | 115/501 |
| videogpa_ti2v5b | 783 | 135 | 648 | 0% | 0% | 22% | 10% | 36% | 31% | 97/308 |
| wan22_i2v_a14b | 783 | 153 | 630 | 1% | 1% | 11% | 8% | 65% | 14% | 69/289 |
| wan_ti2v5b | 755 | 124 | 631 | 1% | 1% | 28% | 11% | 33% | 26% | 104/359 |

### Fig. 3 (v) — generated videos, result kinds per model

| model | videos | not validated (gated) | validated | point estimate | interval | one-sided bound | unidentifiable | not explained | no observation | prompt inside band |
|---|---|---|---|---|---|---|---|---|---|---|
| cogvideox_i2v | 558 | 72 | 486 | 0% | 0% | 30% | 8% | 52% | 10% | 60/341 |
| cosmos | 558 | 72 | 486 | 0% | 3% | 24% | 3% | 57% | 12% | 40/306 |
| cosmos3_nano | 558 | 36 | 522 | 2% | 3% | 25% | 5% | 59% | 7% | 56/356 |
| dynamicrafter_i2v | 558 | 99 | 459 | 0% | 2% | 13% | 7% | 35% | 43% | 53/161 |
| hunyuan15_i2v | 558 | 36 | 522 | 0% | 2% | 18% | 3% | 75% | 2% | 23/331 |
| ltx_i2v | 558 | 36 | 522 | 0% | 0% | 37% | 10% | 46% | 7% | 88/377 |
| minimax_h3 | 463 | 29 | 434 | 5% | 2% | 13% | 6% | 51% | 23% | 47/196 |
| physalign_wan22_i2v_a14b | 558 | 72 | 486 | 0% | 0% | 15% | 6% | 77% | 2% | 45/314 |
| physrvg_ti2v5b | 558 | 72 | 486 | 0% | 0% | 41% | 10% | 48% | 1% | 68/417 |
| videogpa_ti2v5b | 558 | 36 | 522 | 0% | 0% | 25% | 4% | 38% | 33% | 48/262 |
| wan22_i2v_a14b | 558 | 72 | 486 | 0% | 1% | 15% | 2% | 66% | 15% | 52/235 |
| wan_ti2v5b | 531 | 33 | 498 | 0% | 0% | 29% | 5% | 39% | 26% | 44/301 |

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
| physalign_wan22_i2v_a14b | 1.39 (6) | 1.37 (8) | 0.74 (7) |
| physrvg_ti2v5b | 1.38 (9) | 1.41 (18) | 1.01 (9) |
| videogpa_ti2v5b | 2.02 (5) | 2.19 (4) | 1.31 (4) |
| wan22_i2v_a14b | 1.39 (5) | 1.00 (16) | 1.19 (6) |
| wan_ti2v5b | 1.39 (6) | 1.80 (13) | 0.74 (7) |
