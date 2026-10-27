# PhysEdit

**Do image-to-video models follow the physics they are asked for?** PhysEdit gives a model the first frame of a simulated physical event and a prompt that states its physics: gravity, friction or initial speed. We measure the physics in each generated video by inverting the original simulator and compare it with the prompt.

[Generated videos](https://huggingface.co/datasets/phy2/phy2-benchmark-generations) · [PhyDataset](https://huggingface.co/datasets/phy2/phydataset) · [LoRA weights](#data-and-weights) · [中文](README_zh.md)

## Results

12 image-to-video models on 97 Core100 tasks. Every task has 3 prompt variants and 3 seeds, about 870 videos per model. Two groups of metrics score each video:

- **V** compares the video with the reference continuation of its task, which shows the same scene with the prompted physics.
- **P** measures the physical parameters the video shows.

Definitions are in [docs/METRICS.md](docs/METRICS.md).

<table>
<tr><th rowspan="2">Model</th><th colspan="6">V: visual and motion consistency</th><th colspan="6">P: physical parameters</th></tr>
<tr><th>ADE ratio&nbsp;↓</th><th>S-IoU&nbsp;↑</th><th>ST-IoU&nbsp;↑</th><th>PSNR&nbsp;↑</th><th>SSIM&nbsp;↑</th><th>Cam.&nbsp;drift&nbsp;↓</th><th>Explainable&nbsp;↑</th><th>g&nbsp;err.&nbsp;↓</th><th>μ&nbsp;err.&nbsp;↓</th><th>v&nbsp;err.&nbsp;↓</th><th>g&nbsp;τ&nbsp;↑</th><th>v&nbsp;τ&nbsp;↑</th></tr>
<tr><td>CogVideoX-1.5</td><td align="right">1.01</td><td align="right">0.060</td><td align="right">0.003</td><td align="right">24.6</td><td align="right">0.869</td><td align="right">11%</td><td align="right">34.2%</td><td align="right">60.6%</td><td align="right">34.6%</td><td align="right">61.9%</td><td align="right">+0.17</td><td align="right">–</td></tr>
<tr><td>Cosmos-Predict2</td><td align="right">1.04</td><td align="right">0.087</td><td align="right">0.004</td><td align="right">24.5</td><td align="right">0.842</td><td align="right">28%</td><td align="right">31.7%</td><td align="right">60.6%</td><td align="right">34.6%</td><td align="right">45.7%</td><td align="right">+0.56</td><td align="right">+0.62</td></tr>
<tr><td>Cosmos3-Nano</td><td align="right">1.07</td><td align="right">0.185</td><td align="right">0.010</td><td align="right">30.6</td><td align="right">0.933</td><td align="right">4%</td><td align="right">35.0%</td><td align="right">79.5%</td><td align="right">16.2%</td><td align="right">52.7%</td><td align="right">+0.37</td><td align="right">-0.05</td></tr>
<tr><td>DynamiCrafter</td><td align="right">2.09</td><td align="right">0.021</td><td align="right">0.003</td><td align="right">18.8</td><td align="right">0.606</td><td align="right">86%</td><td align="right">19.7%</td><td align="right">79.4%</td><td align="right">39.4%</td><td align="right">21.1%</td><td align="right">+0.33</td><td align="right">+0.24</td></tr>
<tr><td>HunyuanVideo-1.5</td><td align="right">1.26</td><td align="right">0.199</td><td align="right">0.011</td><td align="right">27.9</td><td align="right">0.926</td><td align="right">5%</td><td align="right">20.1%</td><td align="right">60.6%</td><td align="right">34.6%</td><td align="right">61.3%</td><td align="right">+0.95</td><td align="right">+0.64</td></tr>
<tr><td>LTX-Video-2B</td><td align="right">1.03</td><td align="right">0.068</td><td align="right">0.003</td><td align="right">26.5</td><td align="right">0.846</td><td align="right">42%</td><td align="right">41.0%</td><td align="right">60.5%</td><td align="right">33.0%</td><td align="right">–</td><td align="right">+0.80</td><td align="right">–</td></tr>
<tr><td>MiniMax-H3</td><td align="right">1.46</td><td align="right">0.169</td><td align="right">0.009</td><td align="right">23.6</td><td align="right">0.736</td><td align="right">57%</td><td align="right">25.9%</td><td align="right">66.7%</td><td align="right">48.6%</td><td align="right">22.5%</td><td align="right">+0.78</td><td align="right">+0.76</td></tr>
<tr><td>PhysAlign</td><td align="right">1.67</td><td align="right">0.156</td><td align="right">0.004</td><td align="right">29.9</td><td align="right">0.934</td><td align="right">1%</td><td align="right">22.6%</td><td align="right">70.3%</td><td align="right">34.7%</td><td align="right">65.9%</td><td align="right">+0.46</td><td align="right">+1.00</td></tr>
<tr><td>PhysRVG</td><td align="right">1.01</td><td align="right">0.027</td><td align="right">0.001</td><td align="right">29.6</td><td align="right">0.927</td><td align="right">7%</td><td align="right">47.5%</td><td align="right">83.7%</td><td align="right">34.6%</td><td align="right">–</td><td align="right">+0.69</td><td align="right">–</td></tr>
<tr><td>VideoGPA</td><td align="right">1.08</td><td align="right">0.043</td><td align="right">0.004</td><td align="right">22.2</td><td align="right">0.801</td><td align="right">65%</td><td align="right">29.6%</td><td align="right">79.5%</td><td align="right">34.6%</td><td align="right">55.6%</td><td align="right">+0.43</td><td align="right">–</td></tr>
<tr><td>Wan2.2-I2V-A14B</td><td align="right">1.67</td><td align="right">0.081</td><td align="right">0.005</td><td align="right">22.1</td><td align="right">0.723</td><td align="right">60%</td><td align="right">22.1%</td><td align="right">83.4%</td><td align="right">34.7%</td><td align="right">12.3%</td><td align="right">+0.92</td><td align="right">+0.75</td></tr>
<tr><td>Wan2.2-TI2V-5B</td><td align="right">1.04</td><td align="right">0.044</td><td align="right">0.003</td><td align="right">24.4</td><td align="right">0.832</td><td align="right">54%</td><td align="right">37.0%</td><td align="right">79.6%</td><td align="right">34.6%</td><td align="right">50.6%</td><td align="right">+0.43</td><td align="right">–</td></tr>
<tr><td><b>All models</b></td><td align="right"></td><td align="right"></td><td align="right"></td><td align="right"></td><td align="right"></td><td align="right"></td><td align="right">30.6%</td><td align="right">71.8%</td><td align="right">34.6%</td><td align="right">32.6%</td><td align="right">+0.63</td><td align="right">+0.48</td></tr>
<tr><td><i>Physically correct video</i></td><td align="right">0.02</td><td align="right">0.962</td><td align="right">0.891</td><td align="right">37.7</td><td align="right">0.978</td><td align="right">–</td><td align="right">–</td><td align="right">2.4%</td><td align="right">2.7%</td><td align="right">0.7%</td><td align="right">+1.00</td><td align="right">+1.00</td></tr>
<tr><td><i>Condition frame held still</i></td><td align="right">1.00</td><td align="right">0.000</td><td align="right">0.000</td><td align="right">37.0</td><td align="right">0.976</td><td align="right">–</td><td align="right">–</td><td align="right">–</td><td align="right">–</td><td align="right">–</td><td align="right">–</td><td align="right">–</td></tr>
</table>

- **ADE ratio**: trajectory error of the tracked objects divided by that of a video in which nothing moves. Below 1 is closer to the reference than standing still.
- **S-IoU, ST-IoU**: whether motion happens at the right place, and at the right place and time, as defined in Physics-IQ.
- **PSNR, SSIM**: per frame against the reference continuation. A still condition frame scores 37.0 dB, more than any model, so both measure appearance stability rather than physics.
- **Cam. drift**: share of videos whose camera moves by more than 2 % of the image diagonal.
- **Explainable**: share of results whose motion some value of the parameter explains in the original simulator.
- **Error**: median |measured / prompted − 1| over the results that yield a value.
- **τ**: Kendall τ between prompted and measured values across the videos of one task. The 95 % interval over all models is +0.46 to +0.78 for g and +0.10 to +0.73 for v.
- *Italic rows*: the reference re-encoded at 30 fps as a physically correct video, and the condition frame held still.

## Critical-boundary evaluation

Some events change their outcome at a parameter boundary: an object tips over or stays, slides or sticks. This module places samples at known distances on both sides of the reference boundary and checks whether the generated event is correct.

| Metric | Meaning |
|---|---|
| NearAcc | balanced accuracy close to the boundary |
| Distance-stratified accuracy | balanced accuracy per distance bin |
| PairAcc | both samples of a cross-boundary pair are correct |
| EventExact | the whole event chain matches |

`python -m physedit boundary` registers the samples, builds the generation manifests and scores them. `python -m physedit boundary-evaluate` adds quality screening, per-event judging and human review. Protocol: [docs/critical_boundary/CRITICAL_BOUNDARY_PROTOCOL.md](docs/critical_boundary/CRITICAL_BOUNDARY_PROTOCOL.md).

## Why simulator inversion

<p align="center"><img src="docs/figures/inversion_approaches.svg" width="95%"></p>

There are three ways to measure gravity, friction or speed from a single video:

- **2D bounding box** fits the image-plane trajectory of the object's box.
- **Depth lifting** lifts the trajectory to 3D with a depth model.
- **Simulator inversion**, ours, re-simulates the original scene at many parameter values and keeps the values whose rendered boxes match the video.

Only simulator inversion covers contact, friction, rolling and collisions, and only it can tell that no parameter value explains the motion. The method is described in [docs/INVERSION.md](docs/INVERSION.md).

**Development set.** Simulated videos with known parameters, separate from Core100. Every method receives the same tracked boxes and the same camera.

| Method | g error | μ error | v error |
|---|---:|---:|---:|
| 2D bounding box | TBD | – | TBD |
| Depth lifting: DepthPro, Depth Anything V2, ZoeDepth, MoGe-2, UniDepthV2, VGGT | TBD | – | TBD |
| Simulator inversion, ours | TBD | TBD | TBD |

**Known-answer test.** The same pipeline runs on videos whose physics is known: the Core100 reference videos and their re-encodings in the formats of the generated videos.

| Videos with known physics | g error | μ error | v error | g τ | v τ |
|---|---:|---:|---:|---:|---:|
| Core100 reference videos | 2.0% | 2.0% | 0.8% | +1.00 | +1.00 |
| Re-encoded, 15 fps | 2.3% | 2.0% | 0.8% | +1.00 | +1.00 |
| Re-encoded, 30 fps, 121 frames | 2.4% | 2.7% | 0.7% | +1.00 | +1.00 |
| Re-encoded, 10 fps, 16 frames | 2.1% | 2.4% | 0.8% | +1.00 | +1.00 |

The uncertainty bands are calibrated to 95 % coverage on the reference videos. A generated result counts only where the same task in the same video format passes this test.

## Data and weights

| Resource | Content |
|---|---|
| [phy2/phy2-benchmark-generations](https://huggingface.co/datasets/phy2/phy2-benchmark-generations) | Generated videos of the 12 models on Core100 |
| [phy2/phydataset](https://huggingface.co/datasets/phy2/phydataset) | PhyDataset: simulated physical events with per-frame states, known conditions and prompts in English and Chinese; the Core100 tasks come from it |

LoRA weights trained on PhyDataset, from the [Releases](https://github.com/Shuran-z/PhysEdit/releases):

| Base model | Language | Weights |
|---|---|---|
| CogVideoX1.5-5B-I2V | EN | [cogvideox1.5-5b-i2v-phydataset-en-lora-v1](https://github.com/Shuran-z/PhysEdit/releases/tag/cogvideox1.5-5b-i2v-phydataset-en-lora-v1) |
| Wan2.2-TI2V-5B | EN | [wan2.2-ti2v-5b-phydataset-en-lora-v1](https://github.com/Shuran-z/PhysEdit/releases/tag/wan2.2-ti2v-5b-phydataset-en-lora-v1) |
| Wan2.2-TI2V-5B | ZH | [wan2.2-ti2v-5b-phydataset-zh-lora-v1](https://github.com/Shuran-z/PhysEdit/releases/tag/wan2.2-ti2v-5b-phydataset-zh-lora-v1) |
| LTX-Video-2B | EN | [ltx-video-2b-phydataset-en-lora-v1](https://github.com/Shuran-z/PhysEdit/releases/tag/ltx-video-2b-phydataset-en-lora-v1) |
| LTX-Video-2B | ZH | [ltx-video-2b-phydataset-zh-lora-v1](https://github.com/Shuran-z/PhysEdit/releases/tag/ltx-video-2b-phydataset-zh-lora-v1) |

## Usage

```bash
pip install -e .
```

- Evaluate a model: [docs/EVALUATE.md](docs/EVALUATE.md)
- Generation runners of the evaluated models: [docs/phyediting/MODELS.md](docs/phyediting/MODELS.md)
- Critical-boundary module: [BOUNDARY_EVALUATION.md](BOUNDARY_EVALUATION.md)

## Repository

| Path | Content |
|---|---|
| `physprobe/` | Simulator inversion and the V and P metrics |
| `physedit/` | Generation runners and the critical-boundary module |
| `gravtrace/`, `scripts/` | 2D bounding box and depth lifting baselines, analysis scripts |
| `docs/` | Metrics, method and evaluation guide |

## License

MIT, see [LICENSE](LICENSE).
