# Part 2 Python 侧 v1 Baseline — 工作笔记（notebook 体例）

> 对应日期：2026-04-18
> 对应 commit：`c9df7b1 feat: Part 2 Python baseline pipeline and Docker packaging`
> 仓库：https://github.com/ExusiaiHY/BME1307-spring-2026

---

## 0. 今天要解决什么

BUSAT 工具箱还是拿不到（`tamps.cinvestav.mx` 域名解析/访问仍异常），MATLAB 侧 `autosegment` 不可用。为了不让 Part 2 完全被卡住，把 **Python 侧能独立做的部分全部打通到 baseline 能跑**：

- 数据 → 分割 → 特征 → 三种分类器 → 交叉验证 → 标准指标
- 同时把整个项目打包成 Docker（不含数据集，外挂使用）
- 所有产物推到 GitHub

---

## 1. Cell ①  数据对齐

- 数据集：`Breast-ultrasound-samples/Ultrasound Samples/` 下 120 张 `.jpg` + 1 个 `pathology.xlsx`
- 图像 id 从 `2.jpg` 排到 `121.jpg`（没有 1.jpg），`pathology.xlsx` 的第 i 行对应 id = i + 2
- 标签列叫 `P/N`：0=阴性 74 例，1=阳性 46 例（约 1.6:1）
- `src/busat_py/data.py` 里 `load_labels()` 做这个对齐 + 路径拼接 + 文件存在性校验
- `basic_stats()` 用断言保住 `n=120 / P=46 / N=74`，结构一走样就会立刻挂掉

```python
labels = load_labels()          # DataFrame(image_id, label, path)
basic_stats(labels)             # {'n': 120, 'positive': 46, 'negative': 74}
for sample in iter_images(labels):
    sample.image_id, sample.label, sample.image_bgr.shape
```

---

## 2. Cell ②  分割：双路（classical CV + 全 ROI）

BUSAT 的 `autosegment` 暂时没有，就在 Python 里自己拼一个 fallback，同时保留 **把整张 ROI 当作病灶** 的 baseline，好做 A/B。

`src/busat_py/segmentation.py`：

- `segment_full(img)` — 返回全 1 掩膜
- `segment_cv(img)` — 流水线：
  1. 灰度化
  2. `cv2.medianBlur(3)` + 3×3 形态学闭 —— 压住十字测量标记这类小而亮的点
  3. `cv2.GaussianBlur(sigma=1.5)`
  4. `skimage.filters.threshold_otsu` 反向阈值（病灶暗）
  5. `disk(r)` 形态学开、闭清理毛刺（`r = min(h,w)//40`）
  6. `remove_small_objects(min=2% 图像面积)`
  7. 连通域打分 = `area_ratio - 0.5 * normalized_centroid_distance`，挑分最高的一块
  8. 拿不到合格区域就退化成「图像中心 60%×60% 矩形」掩膜

抽样看了 5 张叠加图，问题主要出在紧裁剪且背景也偏暗的 ROI 上 —— Otsu 会把病灶 + 周围等暗组织一起吞进来，病灶边界还是能覆盖住，但形状特征的区分度会被稀释。下次要么上 Chan-Vese refine，要么改成「最暗种子 + 区域生长」。

扫完 120 张：

| 指标 | 值 |
|---|---|
| fallback 次数 | 0 / 120 |
| 前景占比均值 | 0.460 |
| 前景占比中位 | 0.481 |
| 前景占比范围 | 0.135 – 0.737 |

---

## 3. Cell ③  特征提取

`src/busat_py/features.py`，对 `(image, mask)` 出一个 dict，共 **36 维**：

| 类别 | 字段 | 数量 |
|---|---|---|
| 形状（基于最大连通域） | area / perimeter / equivalent_diameter / eccentricity / solidity / extent / circularity (`4πA/P²`) / aspect_ratio / major_axis / minor_axis | 10 |
| 强度（mask 内像素） | mean / std / min / max / median / skew / kurt / p10 / p90 / entropy | 10 |
| GLCM（距离 [1,3]，角度 4 个，32 级量化） | contrast / dissimilarity / homogeneity / ASM / energy / correlation（按角/距均值） | 6 |
| LBP（P=8, R=1, uniform） | 10 桶 histogram | 10 |

对 `mask_full` 和 `mask_cv` 各算一遍，产出两张 120×38 的 CSV：
`outputs/part2/features_full.csv`、`outputs/part2/features_cv.csv`。

---

## 4. Cell ④  分类器

`src/busat_py/classify.py`，三路 Pipeline，全部套 `StandardScaler`，全部 `class_weight='balanced'`（对冲 1.6:1 不平衡）：

- **LogisticRegression**: `C=1`, `L2`, `liblinear`, `max_iter=2000`
- **SVC**: `C=1`, `kernel='rbf'`, `gamma='scale'`, `probability=True`
- **RandomForestClassifier**: `n_estimators=300`, `n_jobs=-1`

这一版不做超参搜索，先抛 baseline 出来；下一轮再补 nested CV。

---

## 5. Cell ⑤  交叉验证 + 指标 + ROC

`src/busat_py/evaluate.py`，`StratifiedKFold(n_splits=5, shuffle=True, random_state=42)`：

- 每折输出：Accuracy、Sensitivity（正类 recall）、Specificity、ROC-AUC
- ROC：每折 `predict_proba` 得分 → `roc_curve`，在统一的 FPR 网格上插值后画 mean±std
- 落盘：`metrics.csv`（每行 mask × model），6 张 `roc_<mask>_<model>.png`

**完整结果（种子 42，复跑两次结果一致）：**

| mask | model | ACC | Sens | Spec | AUC |
|---|---|---|---|---|---|
| full | logreg | 0.825 ± 0.049 | 0.869 | 0.797 | **0.893 ± 0.052** |
| full | svm    | 0.817 ± 0.042 | 0.824 | 0.810 | **0.915 ± 0.022** |
| full | rf     | 0.817 ± 0.057 | 0.718 | 0.878 | 0.880 ± 0.012 |
| cv   | logreg | 0.825 ± 0.055 | 0.849 | 0.810 | 0.890 ± 0.082 |
| cv   | svm    | 0.808 ± 0.062 | 0.782 | 0.825 | 0.854 ± 0.083 |
| cv   | rf     | 0.817 ± 0.057 | 0.804 | 0.825 | **0.917 ± 0.063** |

几个观察：

- `mask_cv + RF` AUC 最高（0.917），`mask_full + SVM` 次之（0.915）且方差最小。
- `mask_full` vs `mask_cv` 整体差异很小 —— 因为数据集本身就是 **紧裁剪** 的 ROI，整张图基本都是相关组织，分割只是进一步挑了「最暗的那块」，空间定位增益有限。
- RF 在 `mask_full` 下 Sensitivity 只有 0.72（特异度却有 0.88），说明它倾向把阳性判成阴性；`mask_cv` 下靠形状特征把 Sens 拉回到 0.80。

---

## 6. Cell ⑥  Docker 封装

`Dockerfile` + `.dockerignore`：

- 基镜像 `python:3.9-slim`
- 系统依赖：`libgl1 libglib2.0-0 libsm6 libxext6 libxrender1`（OpenCV 必需）
- `pip install -r requirements.txt`
- 只 COPY `src/`、`scripts/`、`notebooks/`，**不** COPY 数据集（镜像小）
- 数据集通过 `-v` 外挂到 `/data`：

```bash
docker build -t bme1307-part2 .
docker run --rm \
  -v "$(pwd)/Breast-ultrasound-samples/Ultrasound Samples":/data:ro \
  -v "$(pwd)/outputs":/app/outputs \
  bme1307-part2
```

`config.py` 加了 `BUSAT_DATA_DIR` 和 `BUSAT_OUTPUTS_DIR` 两个 env 覆盖点，所以同一套代码在本地开发和容器里都能用。

**⚠️ 今天本地没装 Docker runtime，build 还没本地验证过。** 等装好 Docker Desktop / OrbStack 再补一次冒烟测试。

---

## 7. Cell ⑦  GitHub 同步

推到了 `origin/main`：

- 17 个文件，+2689 / -21 行
- 新文件：`Dockerfile`、`.dockerignore`、`src/busat_py/*.py`（7 个）、`scripts/run_part2.py`、`notebooks/part2.ipynb`、`outputs/part2/{features_full,features_cv,metrics}.csv`、`outputs/part2/segmentation_report.json`
- 修改：`README.md`（加 Docker/本地运行说明）、`docs/worklog.md`（加今日进展）
- `.gitignore` 按配置把 `*.png`、`Breast-ultrasound-samples/`、`.venv/` 都排除了
- commit：`c9df7b1 feat: Part 2 Python baseline pipeline and Docker packaging`

---

## 8. 已知问题 & 下一步

### 已知问题

1. 经典 CV 分割在紧裁剪 ROI 上精度有限，对形状特征的区分度贡献不如预期
2. Docker 本地尚未 build 验证（环境里没 runtime）
3. 没做超参搜索，现在跑的是一组固定默认超参

### 下一轮要做

- **特征数量对性能的影响**（课程问答题 3）：ANOVA-F / MI 排序 → 从 top-k 扫 k = 1 到 36，画 AUC 随 k 的曲线；看是否存在明显拐点
- **分割误差对分类的影响**（课程问答题 4）：对 `mask_cv` 做 dilate / erode（半径 1/3/5）和中心偏移（3/5/10 px）扰动，重新抽特征再 5-fold CV，报 AUC 下降曲线
- Chan-Vese 或区域生长 refine 分割（看能否把 CV 路的 AUC 拉到 0.93+）
- 等 BUSAT 到手后，用 MATLAB `autosegment` 的掩膜重跑同一批特征，做「BUSAT vs Python 分割」对照

---

## 2026-04-19 Update

### 1. 课程约束重新确认

- 重新看课程说明后，可以明确排除一个误区：**Part 2 并没有要求只能用经典 CV 分割**。
- 课程只是说可以直接使用 BUSAT toolbox 的 `autosegment` 辅助分割；而 Part 1 甚至明确写了“使用课堂所学或自行查阅的任意图像分割技术”。
- 所以合理的项目结构应该是：
  1. 保留 `full` / `cv` baseline，方便做 ablation；
  2. 直接接入更强的 classical 方法；
  3. 等 BUSAT mask 出来后，做 `BUSAT vs refined vs baseline` 对照。

### 2. BUSAT 状态更新

- 现在 BUSAT 不再是“找不到工具箱文件”的状态；本机已经确认存在 `~/Documents/MATLAB/BUSAT/Segmentation/autosegment.m`。
- 我读了 `autosegment.m`，它本质上是一个 **texture-driven automatic segmentation**：`log-Gabor filtering + lattice feature extraction + LDA classification + post-processing`。
- 这意味着当前项目如果还停留在 Otsu baseline，会低估课程允许的方法空间，也低估 BUSAT 本身的复杂度。
- 当前剩余问题变成了自动化集成：Codex 所在的 headless shell 里启动 MATLAB CLI 会触发本机 `Qt/neon` 报错，所以我先把 BUSAT 导出路径铺好，而不是继续把主线卡在 MATLAB 上。

### 3. 分割升级：`refined`

在 `src/busat_py/segmentation.py` 里新增了 `segment_refined()`：

1. `medianBlur(5)` 去 speckle
2. `CLAHE` 拉局部对比
3. 取反得到 hypoechoic lesion 的亮响应
4. 乘一个中心高斯先验，抑制远离 ROI 中心的低回声背景
5. 通过阈值 + 形态学得到 seed
6. 在 seed 周围裁一个 padded patch
7. 用 `morphological Chan-Vese` 做边界细化
8. 再做一次连通域筛选，留下“足够居中且面积合理”的病灶区域

这个方法的目的不是追求 fancy，而是解决之前的真实问题：**紧裁剪 ROI 上病灶和周围低回声组织容易被一起吞进去**。

### 4. Runner 升级

`scripts/run_part2.py` 现在已经不再写死为 `full + cv` 两路，而是支持多策略：

```bash
python scripts/run_part2.py
python scripts/run_part2.py --strategies refined --save-masks
python scripts/run_part2.py --strategies busat --busat-masks-dir outputs/part2/busat_masks
```

- 默认策略：`full / cv / refined`
- 新增输出：`features_refined.csv`
- `segmentation_report.json` 现在按策略分别汇总

同时新增了 `scripts/export_busat_masks.m`，供本机 MATLAB 会话批量导出：

```matlab
export_busat_masks
```

导出的 `outputs/part2/busat_masks/<image_id>_mask.png` 可以被 Python runner 直接读取并纳入统一评估。

### 5. 新结果

`refined` 路线已经完整复跑，120 张图 **0 fallback**，平均前景占比从旧 `cv` 的 **0.460** 降到 **0.243**，边界明显更收敛。

最新 5-fold 结果如下：

| mask | model | ACC | Sens | Spec | AUC |
|---|---|---|---|---|---|
| full    | logreg | 0.825 ± 0.049 | 0.869 | 0.797 | 0.893 ± 0.052 |
| full    | svm    | 0.817 ± 0.042 | 0.824 | 0.810 | 0.915 ± 0.022 |
| full    | rf     | 0.817 ± 0.057 | 0.718 | 0.878 | 0.880 ± 0.012 |
| cv      | logreg | 0.825 ± 0.055 | 0.849 | 0.810 | 0.890 ± 0.082 |
| cv      | svm    | 0.808 ± 0.062 | 0.782 | 0.825 | 0.854 ± 0.083 |
| cv      | rf     | 0.817 ± 0.057 | 0.804 | 0.825 | 0.917 ± 0.063 |
| refined | logreg | 0.825 ± 0.041 | 0.827 | 0.825 | 0.920 ± 0.050 |
| refined | svm    | **0.858 ± 0.057** | 0.824 | 0.877 | **0.924 ± 0.050** |
| refined | rf     | **0.875 ± 0.070** | 0.802 | 0.918 | 0.903 ± 0.054 |

几个直接结论：

- 如果以 **AUC** 作为主指标，目前最好的组合已经从 `cv + RF` 变成了 `refined + SVM`。
- 如果以 **Accuracy** 作为主指标，`refined + RF` 也比旧 baseline 更高。
- 这说明此前对经典 CV 的担忧是成立的，而且已经被更强的 classical segmentation 部分解决。

### 6. 下一步

- 在 MATLAB 会话里实际跑一次 `export_busat_masks`，补齐 BUSAT 掩膜。
- 然后用同一套 feature / classifier / CV 流程做正式的 `BUSAT vs refined vs baseline` 对照。
- 最后再接课程问答题 3 和 4：特征数量影响、分割误差影响。
