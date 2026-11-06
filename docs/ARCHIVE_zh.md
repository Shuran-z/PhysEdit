# 早先的结果

第一批结果：12 个模型，Core100 中的 97 个任务，每个任务 3 种提示词写法、3 个随机种子。视频在生成视频数据集的 `archive/` 目录下。

12 个图生视频模型，Core100 中的 97 个任务。每个任务有 3 种提示词写法、3 个随机种子，每个模型约 870 条视频。每条视频用两组指标评分：

- **V**：和该任务的参考续段比较；参考续段是同一场景在提示物理条件下的真实结果。
- **P**：测量视频表现出的物理参数。

定义见 [docs/METRICS_zh.md](METRICS_zh.md)。

<table>
<tr><th rowspan="2">模型</th><th colspan="6">V：画面与运动一致性</th><th colspan="6">P：物理参数</th></tr>
<tr><th>ADE 比值&nbsp;↓</th><th>S-IoU&nbsp;↑</th><th>ST-IoU&nbsp;↑</th><th>PSNR&nbsp;↑</th><th>SSIM&nbsp;↑</th><th>镜头漂移&nbsp;↓</th><th>可解释率&nbsp;↑</th><th>g&nbsp;误差&nbsp;↓</th><th>μ&nbsp;误差&nbsp;↓</th><th>v&nbsp;误差&nbsp;↓</th><th>g&nbsp;τ&nbsp;↑</th><th>v&nbsp;τ&nbsp;↑</th></tr>
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
<tr><td><b>全部模型</b></td><td align="right"></td><td align="right"></td><td align="right"></td><td align="right"></td><td align="right"></td><td align="right"></td><td align="right">30.6%</td><td align="right">71.8%</td><td align="right">34.6%</td><td align="right">32.6%</td><td align="right">+0.63</td><td align="right">+0.48</td></tr>
<tr><td><i>物理正确的视频</i></td><td align="right">0.02</td><td align="right">0.962</td><td align="right">0.891</td><td align="right">37.7</td><td align="right">0.978</td><td align="right">–</td><td align="right">–</td><td align="right">2.4%</td><td align="right">2.7%</td><td align="right">0.7%</td><td align="right">+1.00</td><td align="right">+1.00</td></tr>
<tr><td><i>条件帧静止不动</i></td><td align="right">1.00</td><td align="right">0.000</td><td align="right">0.000</td><td align="right">37.0</td><td align="right">0.976</td><td align="right">–</td><td align="right">–</td><td align="right">–</td><td align="right">–</td><td align="right">–</td><td align="right">–</td><td align="right">–</td></tr>
</table>

- **ADE 比值**：被跟踪物体的轨迹误差，除以画面完全不动时的误差。小于 1 才说明比不动更接近参考。
- **S-IoU、ST-IoU**：运动发生的位置是否对得上，以及位置和时间是否都对得上，定义同 Physics-IQ。
- **PSNR、SSIM**：逐帧和参考续段比较。条件帧静止不动就有 37.0 dB，高于所有模型，所以这两项衡量的是画面稳定，不是物理。
- **镜头漂移**：镜头移动超过画面对角线 2% 的视频占比。
- **可解释率**：在原始仿真器里，运动能被该参数某个取值解释的结果占比。
- **误差**：给出数值的结果中，|测得值 / 提示值 − 1| 的中位数。
- **τ**：同一任务的视频之间，提示值和测得值的 Kendall τ。全部模型的 95% 区间：g 为 +0.46 到 +0.78，v 为 +0.10 到 +0.73。
- *斜体两行*：参考视频按 30 fps 重编码后的物理正确视频，以及条件帧静止不动。


本表沿用对应发布批次的输入与结果。当前 Core100 的五条 T19 参考已独立替换，其余 95 条沿用冻结 v6；旧批次结果和人工标签不转移到替代视频。当前参考参数与距离见[逐项绑定](critical_boundary/CORE100_DISTANCE_BINDINGS.md)。
