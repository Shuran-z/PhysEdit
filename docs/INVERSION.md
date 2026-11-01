# Simulator inversion

The inversion measures the gravity *g*, the friction *μ* of the main contact and the initial speed *v* that a video shows. It replays the task's own simulation at many parameter values and keeps the values whose rendered motion matches the video.

<p align="center"><img src="figures/inversion_approaches.svg" width="95%"></p>

## Observation

- **Tracking**: SAM 3.1 tracks every moving object of the scene. All objects are prompted together with their boxes at the condition frame, in one pass per video.
- **Camera compensation**: when the camera moves, the background is registered to the first frame and the object boxes are mapped back.
- **Clock**: frames are placed on physical time. A generated video plays at its own frame rate with the playback convention of its reference.

## Simulation libraries

Each Core100 task comes with the authors' original Genesis scene. For every task and parameter the scene is replayed over a grid of values:

| Parameter | Grid |
|---|---|
| g | 0.5 to 25 m/s², steps of 12 % |
| μ | around the true value, steps of 15 % |
| v | around the true value, steps of 12 % |

The true value itself is never in the grid. Where the dynamics bifurcate, half steps and bisection refine the grid.

Each object is compared only inside its predictability window: the frames where repeated simulations agree and a tiny parameter change acts smoothly, to within 1.5 px at the object's distance. Later frames depend on numerical chaos rather than on the parameter.

## Matching

For every library value, the visible part of each object is projected with the task camera, and its image box is compared with the tracked box.

- **Loss**: Huber loss on the box residuals, scaled by the tracking noise of 1.5 px.
- **Onset**: a free time shift of up to 20 frames absorbs the start of the motion, which the prompt does not fix.
- **Objects**: the losses of all objects add up; an object that contradicts the others at the joint optimum is dropped.
- **Not explained**: an object whose best fit over the whole library stays above about 3 σ is explained by no value.

## Estimate

A local quadratic fit in log-parameter locates the minimum. Values within δ of the minimum are indistinguishable, which gives a point or an interval, a one-sided bound at the edge of the grid, or an unidentifiable result when the minimum is not unique. δ is calibrated on the reference videos: δ = 1 covers the true value in 95.4 % of the reference results.

## Validation

The pipeline runs unchanged on videos whose physics is known: the Core100 reference videos, and the same videos re-encoded in the formats of the generated videos, with their frame rate, length, resolution and compression.

| Videos with known physics | g error | μ error | v error | g τ | v τ |
|---|---:|---:|---:|---:|---:|
| Core100 reference videos | 2.0% | 2.0% | 0.8% | +1.00 | +1.00 |
| Re-encoded, 15 fps | 2.3% | 2.0% | 0.8% | +1.00 | +1.00 |
| Re-encoded, 30 fps, 121 frames | 2.4% | 2.7% | 0.7% | +1.00 | +1.00 |
| Re-encoded, 10 fps, 16 frames | 2.1% | 2.4% | 0.8% | +1.00 | +1.00 |

Errors are medians of |measured / true − 1| over the results with a value. τ = 1 means every pair of videos with different true values is ordered correctly.

A generated result counts only if the physically correct video of the same task, in the same format, yields an estimate.
