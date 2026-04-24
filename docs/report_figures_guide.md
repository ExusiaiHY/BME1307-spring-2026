# 最终报告图表指南

> 所有图表位于 `outputs/report_figures/`，可直接插入 Word / LaTeX / Notion。
> 生成命令：`python scripts/build_report_figures.py`

---

## 目录结构

```text
outputs/report_figures/
├── fig1a_part1_diameter_summary.png           # Part 1 直径测量汇总
├── fig1b_part1_classical_vs_sam2.png          # Part 1 经典 vs SAM2 对比
├── fig1c_part1_measurement_table.png          # Part 1 测量参数表
├── fig2a_part2_segmentation_examples.png      # Part 2 四种分割策略视觉对比
├── fig2b_part2_feature_distribution.png       # Part 2 特征分布（阴阳性）
├── fig2c_part2_metrics_comparison.png         # Part 2 AUC/Accuracy 分组对比
├── fig2d_part2_feature_number_impact.png      # Part 2 特征数量对分类性能的影响 ⭐
├── fig2e_part2_segmentation_error_impact.png  # Part 2 分割误差对分类的影响 ⭐
├── fig3a_part3_comparison_table.png           # Part 3 综合指标对比表
├── fig3b_part3_roc_svm_comparison.png         # Part 3 SVM ROC 对比
├── fig3c_part3_roc_rf_comparison.png          # Part 3 RF ROC 对比
├── fig3d_part2_best_busat_svm_roc.png         # Part 2 最佳 ROC (BUSAT+SVM)
├── panel_part1_classical.png                  # Panel: Part 1 经典分割 8 张 overlay
├── panel_part2_roc.png                        # Panel: Part 2 代表性 ROC
├── panel_part3_foundation_roc.png             # Panel: Part 3 Foundation Model ROC
├── panel_part3_sam2_part1.png                 # Panel: Part 3 SAM2 颈动脉分割
└── panel_part3_sam2_part2.png                 # Panel: Part 3 SAM2 乳腺超声示例
```

---

## Part 1：超声图像采集与颈动脉分割

### 推荐插图

| 图号 | 文件名 | 用途 | 说明 |
|------|--------|------|------|
| 1 | `panel_part1_classical.png` | 经典分割结果展示 | 8 张采集图的 overlay 拼图，包含 6 张 B-mode + 2 张 Color Doppler fallback |
| 2 | `fig1a_part1_diameter_summary.png` | 量化结果与文献对比 | 柱状图 + 绿色文献正常范围带 (4.3–7.7 mm)，8/8 在范围内 |
| 3 | `fig1b_part1_classical_vs_sam2.png` | 与 Part 3 SAM2 的对比 | 前两张 SAM2 fallback 明显偏离（3.6 mm 和 9.5 mm），是很好的失败案例 |
| 4 | `fig1c_part1_measurement_table.png` | 测量参数表 | 样本 ID、模态、Gain、Dynamic Range、直径、是否在文献范围内 |

### 报告撰写要点

- **物理单位换算**：说明 `pixel_spacing_mm = depth_mm / image_height = 32 / 512 = 0.0625 mm/px`。
- **BUSAT 适用性**：BUSAT 是针对乳腺超声训练的，其 `train_data.mat` 的纹理特征基于乳腺病灶；颈动脉为管腔结构，与乳腺病灶形态差异大，因此 **不能直接使用 BUSAT 分割颈动脉**。
- **参数变化实验**：本次采集只有 Gain 从 83 dB → 73 dB 的变化（Range 未变），且前两例因 Hough 失败落入相同 fallback，参数影响实验不够充分，可在报告中诚实说明并建议后续补充。

---

## Part 2：乳腺超声图像分类

### 推荐插图

| 图号 | 文件名 | 用途 | 说明 |
|------|--------|------|------|
| 5 | `fig2a_part2_segmentation_examples.png` | 分割策略视觉对比 | 3 个典型样本 × 4 种策略 (full / cv / refined / busat)，直观展示 mask 差异 |
| 6 | `fig2b_part2_feature_distribution.png` | 特征分布 | 6 个关键特征的箱线图（0=良性，1=恶性），支撑特征工程合理性 |
| 7 | `fig2c_part2_metrics_comparison.png` | 分类性能总览 | 分组柱状图：4 策略 × 3 分类器，左 AUC、右 Accuracy，含误差棒 |
| 8 | `fig2d_part2_feature_number_impact.png` | **特征数量影响** ⭐ | 按 RF 重要性逐步增加特征，AUC 在 ~15 个特征后趋于饱和。直接回应题目要求 |
| 9 | `fig2e_part2_segmentation_error_impact.png` | **分割误差影响** ⭐ | Full (无分割) vs BUSAT (最佳分割) 的 AUC 差距 +0.019~+0.060。直接回应题目要求 |
| 10 | `panel_part2_roc.png` | ROC 曲线精选 | 4 张代表性 ROC：full+svm / refined+svm / busat+svm / busat+rf |
| 11 | `fig3d_part2_best_busat_svm_roc.png` | 最佳模型 ROC | BUSAT + SVM，AUC = 0.937 |

### 关键数值（可直接复制到报告正文）

| 策略 | 最佳分类器 | Accuracy | AUC |
|------|-----------|----------|-----|
| full | SVM | 0.817 | 0.915 |
| cv | RF | 0.817 | 0.917 |
| refined | SVM | 0.858 | 0.924 |
| **busat** | **SVM** | **0.892** | **0.937** |
| **busat** | **RF** | 0.883 | **0.940** |

- **Top 3 重要特征**（按 Random Forest）：`shape_minor_axis` > `shape_perimeter` > `shape_area`
- **特征数量影响结论**：使用全部 36 个特征时 SVM AUC 约 0.93；当特征数降至 Top-10 时 AUC 约 0.92，性能损失很小。说明该数据集上 **形状特征是分类的主导因素**，少量高质量特征即可达到接近全量的性能。
- **分割误差影响结论**：`full`（无分割）把整张 ROI 当病灶，形状特征完全失效，AUC 比 `busat` 低 0.019–0.060。这证明 **不精确的分割会引入非病灶组织，直接降低分类性能**。

---

## Part 3：基础模型驱动的分析

### 推荐插图

| 图号 | 文件名 | 用途 | 说明 |
|------|--------|------|------|
| 12 | `panel_part3_sam2_part1.png` | SAM2 颈动脉分割 | 6/8 在文献范围内，前 2 张 fallback 为失败案例 |
| 13 | `panel_part3_sam2_part2.png` | SAM2 乳腺超声分割 | 3 张低 IoU 失败案例 + 3 张高 IoU 成功案例 |
| 14 | `panel_part3_foundation_roc.png` | Foundation Model ROC | OpenCLIP / BiomedCLIP + SVM/RF/LogReg 的 ROC 对比 |
| 15 | `fig3a_part3_comparison_table.png` | 综合对比表 | Part 2 baseline vs Part 3 foundation model 的 Accuracy / AUC 汇总 |
| 16 | `fig3b_part3_roc_svm_comparison.png` | SVM ROC 跨部分对比 | Part 2 (refined/busat) vs Part 3 (OpenCLIP/BiomedCLIP) |

### 关键数值

| 路线 | 最佳组合 | Accuracy | AUC |
|------|----------|----------|-----|
| Part 2 baseline | BUSAT + SVM | **0.892** | 0.937 |
| Part 2 baseline | BUSAT + RF | 0.883 | **0.940** |
| Part 3 FM | BiomedCLIP + SVM | 0.858 | 0.935 |
| Part 3 FM | BiomedCLIP + RF | 0.850 | 0.928 |

- **结论**：BiomedCLIP + SVM (AUC 0.935) 已经非常接近 BUSAT 传统 pipeline (AUC 0.940)，但尚未超越。这提示 **在无微调场景下，domain-specific encoder 可以逼近传统特征工程，但超声专用 foundation model 仍有提升空间**。
- **局限性声明**：
  1. 本次没有纳入 ultrasound-specific segmentation foundation model（目前公开社区缺乏此类权重），分割部分仅评估了 generalist SAM2。
  2. BiomedCLIP 虽然是 biomedical specialist，但任务本质仍是 "image embedding + shallow classifier"，不是端到端超声分类器。

---

## 使用建议

1. **Word 报告**：直接插入 PNG，每张图下方加图注（caption）。
2. **LaTeX**：使用 `\includegraphics[width=\textwidth]{filename}`，建议用 `figure*` 环境做双栏大图。
3. **PPT 汇报**：`panel_*.png` 系列为宽图，适合直接占满一页；`fig2c` 和 `fig2e` 适合作为论证核心图放大展示。
4. **色彩统一**：所有图使用 seaborn "whitegrid" + 统一配色（蓝 `#4c78a8`、橙 `#f58518`、绿 `#59a14f`、红 `#e45756`），可直接混排而不会视觉冲突。
