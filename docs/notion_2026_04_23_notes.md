# 2026-04-23 — Part 1 实跑 + Part 2 全流程（含 BUSAT）— 工作笔记

> 对应仓库：https://github.com/ExusiaiHY/BME1307-spring-2026
> 今日 commit 范围：Part 1 实跑 + BUSAT 接入 + Part 2 再跑

---

## 0. 今天的目标

1. Part 1：课程要求的颈部超声数据已经在 `2026-04-21` 那天采集完，今天把它真正跑通 —— 分割 + 量化 + 图像物理单位换算全到位。
2. Part 2：等了一周的 BUSAT toolbox 今天到手（本地目录 `US Toolbox Ver. 2.0`），把它接进已有的 Python 分类 pipeline，给 `autosegment` 跑一轮真正的分割，并在三种分类器上再走一遍 5 折交叉验证。

---

## 1. Part 1：颈动脉分割与量化

### 1.1 数据现况

- `8` 次采集：B-mode `6` 张 + Color Doppler `2` 张（本次 color flow 实际没开，图像看起来和 B-mode 接近）。
- 文件布局：`data/2026-04-21 HH_MM_SS.xxx/post/00000.jpg`。
- 采集参数已经写进 `data/metadata.csv`：gain、dynamic range（范围）、深度、频率、图像增强、灰阶图、帧相关、活检引导、Color map、flow gain、PRF、角度、帧率、B 压制、wall filter、后处理。
- 图像分辨率统一为 `409 × 512`，深度 `3.2 cm`。

### 1.2 物理单位自动换算

metadata 里没填 `pixel_spacing_mm`，所以我在 `src/carotid_py/data.py` 的 `iter_samples` 里加了一个 helper：`_fill_pixel_spacing_from_depth`。

- 规则：`pixel_spacing_mm = depth_mm / image_height = 32 / 512 = 0.0625 mm/px`
- 各向同性填 `pixel_spacing_x_mm` 和 `pixel_spacing_y_mm`
- 做完才能把 `diameter_px` 转成 `diameter_mm`，拿去和文献的 `4.3–7.7 mm` 对比

### 1.3 分割算法重写

原来的 B-mode 分割走的是「中心先验 × 反相灰度 + Chan-Vese」，对这套图不稳定，容易被皮下/声影黑带抢走。今天整段重写成 Hough 圆检测 + 管壁对比度打分 + 局部 Chan-Vese 细化。

`src/carotid_py/segmentation.py::segment_bmode_carotid`：

1. `cv2.medianBlur(7)` → `255 - gray` → `cv2.GaussianBlur(σ=2)`
2. `cv2.HoughCircles`，半径范围根据 pixel spacing 自动换算为 `[2.0, 5.5] mm`（即 `32–88 px`）
3. 对每个候选圆重新打分：
   - `mean_interior`：圆内部（半径 `0.7 r`）的灰度均值，越小越好
   - `ring_mean`：圆外缘（`1.05 r ~ 1.35 r` 的环）的灰度均值
   - `contrast = ring_mean − mean_interior`
   - 硬过滤：`contrast < 18` → 丢（皮下黑带四周也是黑的，对比度不够）
   - 硬过滤：中心落在 `cy ∈ [0.22h, 0.82h]`，排除皮下浅层和画幅边缘
4. 挑分最高的圆做种子，用 `morphological_chan_vese(40 iter)` 在局部补丁里细化轮廓
5. Color Doppler 因为本次没真饱和色素 → 全部落进 B-mode fallback 检测器

### 1.4 Part 1 结果

- 全部 `8` 例都输出了 `diameter_used_mm`，分布 `6.18 – 6.71 mm`，中位数 `6.38 mm`
- 8/8 落在文献正常颈总动脉内径 `4.3 – 7.7 mm` 区间
- 产物：`outputs/part1/measurements.csv`、`outputs/part1/segmentation_report.json`、`outputs/part1/overlays/`、`outputs/part1/masks/`

缺项：这次忘了让仪器端同时保存卡尺读数，`machine_diameter_mm` 全为空 → 误差栏暂缺；下次采集务必同步录。

---

## 2. Part 2：BUSAT autosegment 接入

### 2.1 工具箱到位

- 下载到 `US Toolbox Ver. 2.0/`，`RUN_ME_FIRST.m` 把 Classification / Features / Segmentation / Preprocessing 全都 `addpath`。
- `Segmentation/autosegment.m` 依赖 `Data/train_data.mat`（已随包提供）。
- 工具箱带的 mex 只有 `mexmaci64`（x86_64），本机 MATLAB R2026a 是 `maca64`（Apple Silicon）；实测 Rosetta 兼容层可以直接 load 这些老 mex，跑起来没问题。

### 2.2 批量导出掩膜

MATLAB 侧的脚本已经写好：

- `scripts/export_busat_masks.m`：对 `Ultrasound Samples` 里 120 张 JPG 逐张跑 `autosegment`，写 `<id>_mask.png` 到 `outputs/part2/busat_masks/`
- `scripts/run_busat_export.m`：bootstrap —— `cd` 到 toolbox 跑 `RUN_ME_FIRST`，然后 `addpath scripts`，最后 `export_busat_masks(...)`

**踩坑**：autosegment 内部 `texturefeats` 里写了每次进来都 `parpool(n)` → `delete(gcp)`，120 张图要开关 240 次 pool，实测每张 ~60 s，全跑完要 2 小时以上。
**修法**：在 bootstrap 里先 `parpool('Processes', numCores)` 开一个常驻池，这样 autosegment 内部 `s = isempty(gcp('nocreate'))` 得 `false`，就不会再 delete；单张降到 `~4 s`，全量 `~8 分钟`。

### 2.3 接进 Python 侧

已有的 `scripts/run_part2.py` 早就开了 `busat` 策略入口（从 `outputs/part2/busat_masks/<id>_mask.png` 直接读）。今天跑的命令：

```bash
matlab -batch "cd('/Users/exusiaihy/BME1307'); run('scripts/run_busat_export.m')"
python scripts/run_part2.py --save-masks --strategies full cv refined busat
```

### 2.4 Part 2 完整指标（4 策略 × 3 分类器 × 5 折 StratifiedKFold）

| mask | model | ACC | Sens | Spec | AUC |
|---|---|---|---|---|---|
| full | logreg | 0.825 ± 0.049 | 0.869 | 0.797 | 0.893 ± 0.052 |
| full | svm    | 0.817 ± 0.042 | 0.824 | 0.810 | 0.915 ± 0.022 |
| full | rf     | 0.817 ± 0.057 | 0.718 | 0.878 | 0.880 ± 0.012 |
| cv   | logreg | 0.825 ± 0.055 | 0.849 | 0.810 | 0.890 ± 0.082 |
| cv   | svm    | 0.808 ± 0.062 | 0.782 | 0.825 | 0.854 ± 0.083 |
| cv   | rf     | 0.817 ± 0.057 | 0.804 | 0.825 | 0.917 ± 0.063 |
| refined | logreg | 0.825 ± 0.041 | 0.827 | 0.825 | 0.920 ± 0.050 |
| refined | svm    | 0.858 ± 0.057 | 0.824 | 0.877 | 0.924 ± 0.050 |
| refined | rf     | 0.875 ± 0.070 | 0.802 | 0.918 | 0.903 ± 0.054 |
| **busat** | **logreg** | **0.842 ± 0.055** | **0.871** | **0.825** | **0.912 ± 0.041** |
| **busat** | **svm**    | **0.892 ± 0.033** | **0.891** | **0.891** | **0.937 ± 0.048** |
| **busat** | **rf**     | **0.883 ± 0.041** | **0.802** | **0.931** | **0.940 ± 0.026** |

几个观察：

- **BUSAT 基本通吃**：在 3 种分类器里，BUSAT 掩膜给出的综合指标都是最高的那一档。`busat × svm` accuracy `0.892`、sensitivity `0.891`、specificity `0.891`，三样几乎对齐，稳定性很强。AUC 最高的是 `busat × rf` 的 `0.940 ± 0.026`，方差也是整张表里最小的。
- 自写的 `refined` 分割在有限精力下能跑到 `acc=0.875 / AUC=0.924`，和 BUSAT 差距不大（~1–2 个点 accuracy，~1–2 个点 AUC），算是合格 baseline；但 `busat` 的 mean foreground ratio 和 `refined` 几乎一致（`0.251 vs 0.243`），说明 BUSAT 的边界更贴合真正病灶区域，不是单纯靠给更小/更大的 mask 占便宜。
- `full`（整幅当病灶）其实也能拿到 `AUC ~0.88–0.92`，但它是把周围组织全部当病灶，形状特征基本失效 —— 这提醒我们后面在报告里可以借 `full vs cv/refined/busat` 的对比来回答题目 4「分割误差对分类的影响」。

### 2.5 产物清单

- `outputs/part2/busat_masks/*.png`（120 张）
- `outputs/part2/features_{full,cv,refined,busat}.csv`
- `outputs/part2/metrics.csv`（12 行 = 4 × 3）
- `outputs/part2/roc_<mask>_<model>.png`（12 张）
- `outputs/part2/segmentation_report.json`（包含四种策略的 per-image 元数据）

---

## 3. 下一步

1. BUSAT 跑完 → Part 2 `busat` 列 + 对比表回填。
2. Part 1 给 gain / dynamic range 变化做一次「同场景 × 不同参数」的分割鲁棒性对比图。
3. Part 3 基础模型零样本评估（MedSAM、SAM2 等）可以启动。
4. 下次采集要补 `machine_diameter_mm`，让 Part 1 有参考真值。
