# 2026-04-24 — Part 3 基础模型评估已跑通

> 对应仓库：https://github.com/ExusiaiHY/BME1307-spring-2026
> 今日 commit 范围：Part 3 实现 + 产物 + notebook

---

## 0. 今天完成了什么

1. 把 Part 3 方案真正落成可运行代码：
   - `scripts/run_part3.py`
   - `src/part3_py/`
   - `notebooks/part3.ipynb`
2. 跑通了两条基础模型路线：
   - **分割**：SAM2 point-prompt zero-shot
   - **分类**：OpenCLIP / BiomedCLIP image embedding + `logreg / svm / rf` + `5-fold CV`
3. 产物已经生成在 `outputs/part3/`，包括：
   - metrics
   - ROC 图
   - Part 1 / Part 2 overlays
   - embeddings 表

---

## 1. Part 3 分割：SAM2

### 1.1 模型选择

- 课程方案里原本写的是 **SAM2 (ViT-B)**。
- 实现时核对后发现，官方发布的 SAM2 checkpoint 使用的是 **Hiera 命名**，不是旧的 ViT-B 命名。
- 因此本次实际使用的是 **`facebook/sam2-hiera-base-plus`**，可以把它理解为这次实验里的 base-size generalist SAM2。

### 1.2 Prompt 设计

- **Part 1（颈动脉）**：
  - 先在图上用 Hough circle 找血管中心，拿这个中心当 point prompt。
  - 如果 Hough 在整图上失败，则退到 ROI crop 内再做 point prompt。
- **Part 2（乳腺超声）**：
  - 直接用图像中心作为 point prompt。

### 1.3 结果

- Part 1 共 `8` 张图：
  - `6` 张直接用了 Hough prompt
  - `2` 张退回到 crop fallback
  - `6 / 8` 张直径落在文献范围 `4.3–7.7 mm`
- Part 2 共 `120` 张图全部跑通：
  - 平均 foreground ratio：`0.249`
  - 平均 centroid offset：`0.045`
  - 平均 SAM2 predicted IoU：`0.680`

### 1.4 需要在报告里说明的点

- **这次没有纳入 ultrasound-specialist segmentation foundation model**。
- 所以 Part 3 的分割对照，本质上是：
  - 一个 generalist segmentation FM：SAM2
  - 对比课程前两部分已有的 classical / BUSAT pipeline

---

## 2. Part 3 分类：OpenCLIP vs BiomedCLIP

### 2.1 方案

- **OpenCLIP**：generalist image encoder
- **BiomedCLIP**：biomedical specialist image encoder
- 做法：提图像 embedding，然后直接丢给已存在的
  - `logreg`
  - `svm`
  - `rf`
  进行 `5-fold Stratified CV`

### 2.2 Foundation-model 结果

| encoder | model | accuracy | AUC |
|---|---|---:|---:|
| OpenCLIP | logreg | 0.833 | 0.916 |
| OpenCLIP | svm    | 0.833 | 0.883 |
| OpenCLIP | rf     | 0.808 | 0.867 |
| BiomedCLIP | logreg | 0.817 | 0.860 |
| **BiomedCLIP** | **svm** | **0.858** | **0.935** |
| BiomedCLIP | rf | 0.850 | 0.928 |

- foundation-model 组内最优是 **BiomedCLIP + SVM**

### 2.3 与 Part 2 baseline 对比

- Part 2 当前最好 accuracy：**BUSAT + SVM = 0.892**
- Part 2 当前最好 AUC：**BUSAT + RF = 0.940**
- 因此这次 Part 3 最好的 foundation-model 结果：
  - **BiomedCLIP + SVM**
  - `accuracy = 0.858`
  - `AUC = 0.935`

已经非常接近 BUSAT 传统 pipeline，但还没有超过它。

---

## 3. 当前判断

- Part 3 已经不是“方案”，而是 **真正可复现实验**。
- 可以直接从 `outputs/part3/` 里拿图和表进报告：
  - `metrics/classification_comparison.csv`
  - `roc/roc_compare_{logreg,svm,rf}.png`
  - `overlays/part1_sam2/*.png`
  - `overlays/part2_sam2/*.png`

---

## 4. 下一步

1. 从 `classification_comparison.csv` 里抽一张最终结果表，直接放进报告。
2. 选 Part 1 成功 / 失败 overlay 各几张，作为 zero-shot FM 分割优缺点示例。
3. 在报告讨论里明确写出：
   - SAM2 是 generalist segmentation FM
   - 没有纳入 ultrasound-specialist segmentation FM
   - BiomedCLIP 虽然是 biomedical specialist，但这里仍然是 embedding + shallow classifier 的路线，不是专门针对超声训练的端到端模型
