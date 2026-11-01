# Metrics

Every generated video belongs to a Core100 task: a simulated reference video, its condition frame, which is frame 5, and a prompt that states the physical parameters. The metrics form two groups:

- **V** compares the generated video with the reference continuation of the task.
- **P** measures the physical parameters the generated video shows.

## V: visual and motion consistency

The window starts at the condition frame and lasts 5 s, or until the shorter video ends. Frames are aligned on physical time; a generated video plays at its own frame rate. Generated frames are mapped into the reference image through the registration of the condition frame.

| Metric | Definition |
|---|---|
| ADE, FDE | Box centres of the tracked objects, from SAM 3.1 with camera compensation. Per object, the displacement since the condition frame is compared with the reference on a 30 Hz grid and divided by the image diagonal. ADE averages over time, FDE takes the last common time. Medians over videos. |
| ADE ratio | ADE divided by the ADE of a video in which nothing moves, that is the mean displacement of the reference objects. Below 1 is closer to the reference than standing still. |
| S-IoU, ST-IoU, W-IoU, MSE | Motion agreement as in Physics-IQ. Motion masks come from frame differences on a 10 Hz grid at 427 × 240, grey, with a 5 × 5 blur and a threshold of 0.03. S-IoU compares where motion ever happens, ST-IoU where and when, W-IoU where and how much. MSE is the mean squared RGB difference. |
| Moving pixels | Share of pixels that move per 0.1 s; 0.21 % in the reference continuations. |
| PSNR, SSIM | Every 10 Hz frame after the condition frame against the reference frame at the same physical time, RGB at 427 × 240, SSIM with a Gaussian window of σ = 1.5; averaged per video. |
| Camera drift | Largest background shift relative to the first frame, divided by the image diagonal; reported as the median and as the share of videos above 2 %. |

Two reference rows bound these metrics. The physically correct video is the reference itself, re-encoded in the generated formats. The condition frame held still shows what a video scores by not moving at all.

The still frame reaches 37.0 dB PSNR and 0.976 SSIM, as high as the physically correct videos and higher than every model. Across models, PSNR follows the share of moving pixels with ρ = −0.92 and the camera drift with ρ = −0.96, so PSNR and SSIM report appearance stability, not physics.

## P: physical parameters

The parameters are gravity *g*, the friction *μ* of the main contact and the initial speed *v*, where the task defines them. For each video and parameter the [simulator inversion](INVERSION.md) returns one result:

| Result | Meaning |
|---|---|
| Value | a point estimate or a bounded interval |
| Bound | only a lower or an upper bound is determined |
| Unidentifiable | separated values explain the motion equally well |
| Not explained | no value of the parameter explains the motion |
| No observation | the tracked objects give too few usable frames |

| Metric | Definition |
|---|---|
| Explainable | 1 − not explained − no observation: the share of results whose motion some parameter value explains. |
| g, μ, v error | Median of \|measured / prompted − 1\| over the results with a value. For μ the prompted value is the friction the prompt declares for the measured contact; when both materials are declared, the larger one, as the simulator combines them. |
| g, v response τ | Within one model and one task, every pair of videos with different prompted values is ordered by the measured uncertainty bands. One-sided bounds count as half-open bands, and pairs with overlapping bands stay undecided. τ = concordant − discordant, divided by the decided pairs. The 95 % interval is bootstrapped over model–task groups. μ hardly varies within a task and gets no response score. |

A result enters the statistics only if the physically correct video of the same task, in the same format, yields an estimate. Where it does not, the measurement cannot explain correct physics either.

Across the 12 models, explainability follows the ADE ratio with ρ = −0.90, so it reflects real motion quality. The g response correlates with no V metric beyond |ρ| = 0.43: it measures whether the motion follows a change of the prompted physics, which the V metrics do not capture.

## All V metrics

| | ADE ↓ | FDE ↓ | ADE ratio ↓ | S-IoU ↑ | ST-IoU ↑ | W-IoU ↑ | MSE ↓ | Moving pixels | PSNR ↑ | SSIM ↑ | Drift, median ↓ | Drift > 2 % ↓ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CogVideoX-1.5 | 0.0296 | 0.0555 | 1.01 | 0.060 | 0.003 | 0.045 | 0.0053 | 2.15% | 24.65 | 0.869 | 0.0011 | 11% |
| Cosmos-Predict2 | 0.0353 | 0.0598 | 1.04 | 0.087 | 0.004 | 0.049 | 0.0082 | 2.04% | 24.53 | 0.842 | 0.0010 | 28% |
| Cosmos3-Nano | 0.0388 | 0.0700 | 1.07 | 0.185 | 0.010 | 0.114 | 0.0015 | 0.54% | 30.62 | 0.933 | 0.0002 | 4% |
| DynamiCrafter | 0.0174 | 0.0353 | 2.09 | 0.021 | 0.003 | 0.011 | 0.0171 | 18.34% | 18.78 | 0.606 | 0.0947 | 86% |
| HunyuanVideo-1.5 | 0.0479 | 0.0658 | 1.26 | 0.199 | 0.011 | 0.070 | 0.0028 | 1.74% | 27.87 | 0.926 | 0.0005 | 5% |
| LTX-Video-2B | 0.0312 | 0.0592 | 1.03 | 0.068 | 0.003 | 0.037 | 0.0102 | 3.70% | 26.52 | 0.846 | 0.0053 | 42% |
| MiniMax-H3 | 0.0367 | 0.0795 | 1.46 | 0.169 | 0.009 | 0.097 | 0.0109 | 7.27% | 23.61 | 0.736 | 0.0375 | 57% |
| PhysAlign | 0.0671 | 0.1043 | 1.67 | 0.156 | 0.004 | 0.086 | 0.0015 | 0.36% | 29.89 | 0.934 | 0.0001 | 1% |
| PhysRVG | 0.0237 | 0.0521 | 1.01 | 0.027 | 0.001 | 0.017 | 0.0022 | 1.38% | 29.59 | 0.927 | 0.0007 | 7% |
| VideoGPA | 0.0161 | 0.0365 | 1.08 | 0.043 | 0.004 | 0.022 | 0.0152 | 10.06% | 22.24 | 0.801 | 0.0671 | 65% |
| Wan2.2-I2V-A14B | 0.0517 | 0.0921 | 1.67 | 0.081 | 0.005 | 0.040 | 0.0101 | 7.20% | 22.09 | 0.723 | 0.0388 | 60% |
| Wan2.2-TI2V-5B | 0.0275 | 0.0520 | 1.04 | 0.044 | 0.003 | 0.018 | 0.0090 | 7.42% | 24.44 | 0.832 | 0.0281 | 54% |
| *Physically correct, 15 fps* | 0.0007 | 0.0008 | 0.02 | 0.863 | 0.604 | 0.749 | 0.0003 | 0.20% | 36.41 | 0.976 | – | – |
| *Physically correct, 30 fps, 121 frames* | 0.0006 | 0.0007 | 0.02 | 0.962 | 0.891 | 0.939 | 0.0002 | 0.23% | 37.72 | 0.978 | – | – |
| *Physically correct, 10 fps, 16 frames* | 0.0007 | 0.0006 | 0.10 | 0.930 | 0.833 | 0.892 | 0.0002 | 0.24% | 37.64 | 0.977 | – | – |
| *Condition frame held still* | 0.0348 | 0.0552 | 1.00 | 0.000 | 0.000 | 0.000 | 0.0008 | 0.00% | 37.02 | 0.976 | – | – |

Means over videos; ADE, FDE and the ADE ratio are medians.
