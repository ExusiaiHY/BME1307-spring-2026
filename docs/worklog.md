# BME1307 工作日志

## 2026-04-17

### 今日进展

- 确认 Part 2 所需乳腺超声数据集已经在本地，目录为 `Breast-ultrasound-samples/Ultrasound Samples`。
- 核对数据规模，共有 `120` 张超声图像和 `120` 条病理标签。
- 核对标签分布，阴性 `74` 例，阳性 `46` 例。
- 为 Python 流程补装 `openpyxl`，现在已经可以正常读取 `pathology.xlsx`。
- 确认 MATLAB 已安装在 `/Applications/MATLAB_R2026a.app/bin/matlab`，但当前 shell 的 `PATH` 中没有 `matlab` 命令。
- 检查 MATLAB 可见路径、常见 add-on 目录和仓库内容，暂时没有发现 `BUSAT` 或 `autosegment.m`。

### 当前阻塞

- Part 2 当前最大的阻塞是 `BUSAT toolbox` 无法获得。
- 课程说明中的官方地址 `www.tamps.cinvestav.mx` 无法解析。
- 去掉 `www` 后，`tamps.cinvestav.mx` 返回 `403 Acceso restringido`。
- 在本机现有环境中，`autosegment` 仍然是 `not found`，因此还不能按课程要求直接调用 BUSAT 完成分割。

### 当前判断

- Python 侧的数据整理、特征提取、分类器搭建已经可以启动。
- 但如果要严格按课程描述使用 BUSAT 的 `autosegment`，仍需先拿到可用的 BUSAT 工具箱文件。

## 2026-04-18

### 今日进展

- 完成 GitHub 同步，当前远端已经包含 Part 2 准备阶段的依赖和日志更新。
- 完成 Notion 集成连通性配置，现在已经可以从当前环境向项目日志页写入内容。
- 将工作日志整理为按天记录的格式，后续不再按每次 commit 单独记一条。

### 当前阻塞

- 当前最大的阻塞没有变化，仍然是 `BUSAT toolbox` 还无法下载或定位到可用文件。
- 在没有 BUSAT 的情况下，MATLAB 中无法找到 `autosegment`，这会影响 Part 2 按原始要求启动。

### 下一步

- 优先继续寻找 BUSAT 的可用来源，或从老师、助教、同学、作者处获取工具箱文件。
- 一旦拿到 BUSAT 并确认 `autosegment` 可调用，就开始搭建 Part 2 的完整分割与分类流程。
- 如果短时间内仍无法获得 BUSAT，则先推进 Python 侧的数据整理、特征工程和分类 baseline，保证 Part 2 其余部分不被完全卡住。

## 2026-04-23

### 今日进展

- Part 1 颈部超声数据已经采集完毕并完成打标：共 `8` 次采集（`6` 张 B-mode，`2` 张 Color Doppler），全部放在 `data/2026-04-21 HH_MM_SS.xxx/post/00000.jpg`，随采集参数写进 `data/metadata.csv`。
- 图像分辨率统一为 `409 × 512`，扫描深度 `3.2 cm`，因此在 `carotid_py.data` 中新增了一条自动换算：当 metadata 没填 `pixel_spacing_mm` 时，按 `depth_mm / image_height` 折算出 `0.0625 mm/px`，Part 1 的面积/直径才有物理单位。
- 重写 `carotid_py.segmentation.segment_bmode_carotid`：
  - 在反相灰度图上跑 `HoughCircles` 寻找血管尺寸（`~2–5.5 mm` 半径）的暗色圆形候选。
  - 对每个候选用 `内腔平均强度 + 管壁亮环对比度 + 位置约束`（剔除皮下浅层和靠边的候选）重新打分。
  - 选中后在局部补丁里用 morphological Chan-Vese 细化边界，给出真实掩膜。
- Part 1 现在 8 个样本全部能跑出结果，`diameter_used_mm` 分布在 `6.18–6.71 mm`，中位数 `6.38 mm`，全部落在文献正常颈总动脉内径 `4.3–7.7 mm` 区间内。
- Color Doppler 采集本次仪器没有真正开 color flow，图像里没有饱和色素，因此 `segment_color_doppler` 自动回退到 B-mode 检测器，两张也都得到了颈动脉候选。
- Part 2 流程在完整 `120` 例乳腺超声上跑通，四种分割（`full / cv / refined / busat`）× 三种分类器（`logreg / svm / rf`）× 5 折分层交叉验证已完成。
- BUSAT toolbox 今天到手，放在仓库根目录 `US Toolbox Ver. 2.0/`，`autosegment` + `train_data.mat` 都齐全。
  - MATLAB 侧：`scripts/run_busat_export.m` 做 bootstrap（`cd` 工具箱 → `RUN_ME_FIRST.m` → 预开 `parpool` → `export_busat_masks`）。
  - 关键修正：autosegment 内部 `texturefeats` 每张图都会开/关一次 parpool，原样跑 120 张要 2 小时+；bootstrap 里先开一个常驻池，autosegment 内部就不会 delete 它，单张降到 `~4 s`，全量跑完 `~8 分钟`。
  - toolbox 随包只带 `mexmaci64`（Intel）mex，本机 MATLAB R2026a 是原生 Apple Silicon（maca64），Rosetta 兼容层实测可以直接 load，没再单独编译。
  - Python 侧 `scripts/run_part2.py::_load_busat_mask` 加了 padding 逻辑：autosegment 会把图裁到 `16 px` 的倍数，输出 mask 比原图小最多 15 px，现在 top-left 对齐后用 0 填满到原始尺寸。
- Part 2 最新完整指标：
  - `busat × svm`：**accuracy 0.892，sens 0.891，spec 0.891**，三个指标对齐，稳定性最好。
  - `busat × rf`：**AUC 0.940 ± 0.026**，是整张表里 AUC 均值最高、方差最小的组合。
  - 自写 `refined × svm` 的 AUC `0.924` 与 BUSAT 相差约 1–2 个点，说明自定义 pipeline 与 BUSAT 在该数据集上量级相当。
  - `full`（整幅当病灶）在 RF 上也能达到 AUC `0.88`，但它抹掉了形状特征的区分度；这恰好给了「分割误差对分类影响」这道题一个直接对比素材。
- 产物：`outputs/part2/busat_masks/*.png`（120）、`features_{full,cv,refined,busat}.csv`、`metrics.csv`（12 行）、`roc_<mask>_<model>.png`（12 张）、`segmentation_report.json`。

### 当前阻塞

- Part 1 的机器侧人工测量 (`machine_diameter_mm`) 这次没有记录，误差栏暂时留空；下次采集记得让仪器端也保存卡尺读数，作为分割结果的参考值。

### 下一步

- 让 Part 1 的 Hough 检测在遇到颈内静脉 / 颈总动脉同框时，能用规则（血管位置、脉动 / 可压缩性的间接线索）再区分一次，而不是简单选最圆最黑的那个。
- 若后续有时间，把 Part 1 的 overlays 截进报告，并补充 gain / dynamic range 变化对分割鲁棒性的对比实验。
- Part 3 基础模型评估可以开始动手，先从通用分割基础模型（MedSAM、SAM2 等）在 Part 1 上的零样本表现入手。

## 2026-04-24

### 今日进展

- 完成 Part 3 的完整实现与实跑，新增入口脚本 `scripts/run_part3.py`，并将逻辑拆分到 `src/part3_py/`，包括配置、模型加载、SAM2 prompt 分割、embedding 分类与 ROC 对比绘图。
- Foundation model 分割路线采用 **SAM2 base-size checkpoint**：
  - 课程方案里写的是 “SAM2 (ViT-B)”，但官方发布的 SAM2 权重采用 **Hiera** 命名而不是旧的 ViT-B 命名，因此实现上实际使用的是 `facebook/sam2-hiera-base-plus`。
  - Part 1：优先对整图用 Hough circle 找颈动脉中心作为 point prompt；若全图 Hough 失败，则退回到 ROI crop 内再用中心 prompt，并在 3 个候选 mask 里优先选更小的候选，避免把整块组织吞进去。
  - Part 2：统一用图像中心作 point prompt，对 `120` 张乳腺超声图逐张跑 SAM2，并导出 overlay。
- Foundation model 分类路线采用图像 embedding：
  - **OpenCLIP** 作为 generalist encoder：`ViT-B-32 / laion2b_s34b_b79k`
  - **BiomedCLIP** 作为 biomedical specialist encoder：`microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224`
  - 将两种 encoder 的图像 embedding 接入 Part 2 现有的 `logreg / svm / rf` + `5-fold Stratified CV` 评估器，复用已有度量与 ROC 绘图逻辑。
- 产物已经落在 `outputs/part3/`：
  - `metrics/part1_sam2_measurements.csv`
  - `metrics/part2_sam2_manifest.csv`
  - `metrics/classification_foundation_models.csv`
  - `metrics/classification_comparison.csv`
  - `roc/*.png`
  - `overlays/part1_sam2/*.png`
  - `overlays/part2_sam2/*.png`
  - `embeddings/part2_embeddings_{openclip,biomedclip}.csv`
- 新增 `notebooks/part3.ipynb`，可以直接查看：
  - Part 1 overlay grid
  - Part 2 overlay grid
  - Part 2 baseline vs Part 3 foundation models 的 ROC 对比图
- Notion 同步脚本 `scripts/sync_notion_notes.py` 已补上图片块支持，新增 `docs/notion_2026_04_24_figures.md` 用于把 Part 1 / Part 2 / Part 3 的成果图补充同步到项目日志页。

### Part 3 结果摘要

- Part 1 SAM2：
  - 共 `8` 张图，`6` 张直接使用 Hough point prompt，`2` 张使用 crop fallback。
  - `6 / 8` 张的 `diameter_used_mm` 落在文献正常颈总动脉内径 `4.3–7.7 mm` 区间。
  - 前两张 fallback 样本仍明显不稳定，后续在报告中需要明确说明这属于 zero-shot prompt segmentation 的失败案例。
- Part 2 SAM2 segmentation：
  - `120` 张图全部跑通，平均 foreground ratio `0.249`，平均 centroid offset `0.045`，平均 SAM2 predicted IoU `0.680`。
- Part 3 foundation-model classification：
  - `OpenCLIP + logreg`：accuracy `0.833`，AUC `0.916`
  - `BiomedCLIP + svm`：accuracy `0.858`，AUC `0.935`
  - 在 foundation-model 组内，最优组合是 **BiomedCLIP + SVM**
- 与 Part 2 baseline 对比：
  - Part 2 现有最优 accuracy 仍是 `BUSAT + SVM = 0.892`
  - Part 2 现有最优 AUC 仍是 `BUSAT + RF = 0.940`
  - 因此本次 Part 3 的最好 foundation-model 结果（`BiomedCLIP + SVM`, AUC `0.935`）已经非常接近 BUSAT 传统 pipeline，但还没有超过它。

### 当前判断

- Part 3 现在已经具备“可复现实验 + 可直接截图进报告”的最低完整形态，不再只是方案草图。
- 报告中需要明确写出：
  - **没有找到 ultrasound-specialist segmentation foundation model** 纳入本次对照，分割部分因此只做了 SAM2 这条 generalist 路线。
  - BiomedCLIP 虽然是 biomedical specialist，但任务本质仍是“用通用 image embedding 做 shallow classifier”，不是端到端超声专用分类器。

### 下一步

- 从 `outputs/part3/metrics/classification_comparison.csv` 中提炼一张最终汇总表，直接用于报告正文。
- 挑 2–4 张 Part 1 的成功 / 失败 overlay，加上 4–6 张 Part 2 overlay，放进 Part 3 小节。
- 在报告讨论里加入一段解释：为什么 BiomedCLIP 接近甚至逼近 BUSAT 特征工程，但 Part 1 的零样本 SAM2 仍然容易被 prompt 质量限制。
