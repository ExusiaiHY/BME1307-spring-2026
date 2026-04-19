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

### 今日进展（Part 2 Python 侧 v1 baseline）

- 在 BUSAT 仍未到位的情况下，按「经典 CV 分割 + 全 ROI」双路推进 Python 侧 baseline。
- 搭建 `src/busat_py/` 包：`config` / `data` / `segmentation` / `features` / `classify` / `evaluate`，入口脚本 `scripts/run_part2.py`，演示用 `notebooks/part2.ipynb`。
- 分割：灰度 + 中值/闭运算抑制十字测量标记 → Otsu 反向阈值 → 形态学开闭 → 面积过滤 → 选择中心性最强的连通域；全部 120 张无 fallback，平均前景占比 0.460。
- 特征：形状 10 + 强度 10 + GLCM 6 + LBP 10 uniform 桶，共 36 维；对每张图同时基于 `mask_full` 与 `mask_cv` 各产出一套，落 `features_full.csv` / `features_cv.csv`。
- 分类：LogReg / SVM (RBF) / RandomForest 三路 Pipeline（StandardScaler + `class_weight='balanced'`），StratifiedKFold(5) 评估。
- 指标：ACC ≈ 0.81–0.83，AUC ≈ 0.85–0.92。其中 `mask_cv + RandomForest` AUC 0.917±0.063，`mask_full + SVM` AUC 0.915±0.022。
- 产出：`outputs/part2/` 下的 features CSV、`metrics.csv`、6 张 ROC 曲线、`segmentation_report.json`、120 张分割 mask PNG，种子 42 复跑两次结果一致。

### 已知问题 / 下次迭代

- 经典 CV 分割对部分 ROI 会把病灶与周围低回声组织一起吞进来，后续要么换 Chan-Vese 细化，要么改为以「最暗种子 + 区域生长」约束前景，给形状特征更高区分度。
- 「特征数量对性能的影响」「分割误差对分类的影响」两个课程问答题还没实验，下一轮基于现有 `features_*.csv` 做：ANOVA/MI 排序 + 特征数量扫描曲线；对 `mask_cv` 做 dilate / erode / shift 扰动生成扰动后特征再走一次 CV。
- 超参调优（nested CV）、深度特征、与 BUSAT 结果的对照，都要等 BUSAT 到手后再补。

### Docker 封装

- 写了 `Dockerfile`（python:3.9-slim + OpenCV 运行时依赖 + requirements.txt + 代码）和 `.dockerignore`（把数据集、`.venv`、`outputs/` 排除在 build context 之外）。
- 数据集用外挂卷的方式：`BUSAT_DATA_DIR` 环境变量覆盖 `config.py` 里的数据路径，容器内默认指向 `/data`；`config.py` 同时支持 `BUSAT_OUTPUTS_DIR`。
- `README.md` 补了 `docker build` / `docker run -v` 的用法示例。
- **尚未本地 build 验证**（当前机器没装 Docker runtime），等装好 Docker Desktop / OrbStack 后再做一次冒烟测试。

### Notion 同步

- 通过 Notion REST API（`@notionhq/notion-mcp-server` 官方同款 internal integration token）把今天的 Part 2 笔记同步到「BME1307 Project 日志」页面（page id `344e41c3-0079-8032-bbfd-fcc5365e5ac0`）。
- 推送内容：
  1. `docs/notion_part2_notes.md` —— 8 个 cell 体例的中文工作笔记（83 blocks，含结果表格）。
  2. `notebooks/part2.ipynb` 的完整渲染 —— markdown cell → 文本 block，code cell → Python code block，image/png output → 通过 `/v1/file_uploads` 上传后以 image block 嵌入，text/html DataFrame → Notion 原生 table（36 blocks）。
- 实现小坑：macOS 系统 Python 的 LibreSSL 在 `api.notion.com/v1/file_uploads` 握手阶段会抛 `SSLEOFError`，`urllib` 和 `requests` 都受影响；解决办法是改用 `curl` 子进程做 `file_uploads` 创建和二进制上传，其余 JSON 调用仍走 `urllib`。
- 后续要重复同步，可复用 `/tmp/push_notes_to_notion.py` 和 `/tmp/push_notebook_to_notion.py`（没提交进仓库，避免把 token 相关流程混进主线；要持久化的话可以搬到 `scripts/notion/` 下）。

### 阶段状态总结（截至 2026-04-18）

#### 现在进度如何

- Part 2 已经不是空转状态，Python 侧 baseline 已经完整打通：数据对齐、分割、36 维特征提取、三种分类器、5 折交叉验证、指标汇总、ROC 图和结果文件都已经产出。
- 当前仓库已经具备可复跑的代码骨架：`src/busat_py/`、`scripts/run_part2.py`、`notebooks/part2.ipynb`、`outputs/part2/` 和 Docker 打包文件都已就位。
- 就课程要求覆盖度看，Part 2 的「特征提取 + 至少三种分类器 + 交叉验证 + ACC/Sens/Spec/AUC」主干已经有第一版结果；还缺的是 BUSAT 对照、特征数量影响实验、分割误差影响实验，以及 Docker 本地冒烟验证。

#### 有什么进展

- 数据已经核对清楚：120 张图像，标签分布为阴性 74 / 阳性 46。
- 经典 CV 分割已经能稳定扫完整个数据集，`segmentation_report.json` 显示 120/120 无 fallback，平均前景占比约 0.460。
- baseline 分类结果已经可用：`mask_cv + RandomForest` 的 AUC 达到 0.917 ± 0.063，`mask_full + SVM` 的 AUC 为 0.915 ± 0.022，整体 ACC 约 0.81–0.83，说明即使 BUSAT 还没到位，Python 侧已经能先把分类主线推进起来。
- GitHub 和 Notion 都已经打通，当前阶段的代码、日志和 Part 2 笔记都已同步，后续增量记录成本明显降低。

#### 最大的痛点在哪里

- 最大痛点仍然是 `BUSAT toolbox` 缺失，而且这不是实现细节问题，而是外部依赖问题。课程说明默认 Part 2 可以直接调用 BUSAT 的 `autosegment`，但当前官方地址不可用，本机也找不到可执行的 `autosegment`。
- 这个阻塞的影响不是“完全做不了”，而是“做出来的 Python baseline 还不能和课程指定工具链对齐”。也就是说，现阶段能先完成一个合理的替代 pipeline，但还缺少和 BUSAT 分割结果的对照，以及严格按原题描述复现实验的那一步。
- 第二层痛点是现有经典 CV 分割虽然稳定，但对紧裁剪 ROI 的边界细化有限，病灶和周围低回声组织容易一起被吞进去，导致形状特征增益没有拉开。这会影响后面两道课程问答题，尤其是「分割误差对分类的影响」分析深度。

## 2026-04-19

### 今日进展

- 重新核对课程说明后，明确了一点：Part 2 并没有要求“只能使用经典 CV 分割”。课程给的是 `BUSAT autosegment` 这条推荐路径，但方法上并不封死，保留 baseline 并引入更强分割是合理且更符合报告结构的做法。
- 在本机发现并确认了 BUSAT toolbox 已安装在 `~/Documents/MATLAB/BUSAT`，`autosegment.m`、相关预处理和特征模块都已落地，说明“工具箱缺失”这个一级阻塞已经从资源问题变成了集成问题。
- 阅读了 `autosegment.m` 的实现，确认 BUSAT 本身也不是简单阈值法，而是 `log-Gabor + texture lattice classification + post-processing` 的自动分割流程；因此把 Part 2 仅限缩为传统 Otsu baseline 并不符合课程和工具链的真实上限。
- 在 Python 侧新增 `refined` 分割策略：`center-prior seed + morphological Chan-Vese`，目标就是解决紧裁剪 ROI 里病灶与周边低回声组织粘连的问题。
- `scripts/run_part2.py` 已改成多策略 runner，默认同时评估 `full / cv / refined`，并支持在未来直接接入预导出的 `busat` mask。
- 新增 `scripts/export_busat_masks.m`，用于在本机 MATLAB 中批量导出 `autosegment` 掩膜到 `outputs/part2/busat_masks/`，后续 Python runner 可以直接用这些 PNG 做 BUSAT 对照实验。

### 结果更新

- 新增输出：`outputs/part2/features_refined.csv`。
- `segmentation_report.json` 现在按策略分别汇总；其中 `refined` 在 120/120 样本上无 fallback，平均前景占比约 `0.243`，明显小于旧 `cv` 的 `0.460`，说明边界更收敛。
- 5 折交叉验证下，新的最佳结果来自 `refined + SVM`：
  - Accuracy = `0.858 ± 0.057`
  - Sensitivity = `0.824`
  - Specificity = `0.877`
  - AUC = `0.924 ± 0.050`
- 如果看 Accuracy，`refined + RandomForest` 达到 `0.875 ± 0.070`，也优于旧 baseline。
- 相比之下，旧 `cv + RF` 的 AUC 为 `0.917 ± 0.063`，`full + SVM` 为 `0.915 ± 0.022`。结论很明确：经典 Otsu 路线已经不是当前仓库里最优的 classical segmentation 方案。

### 当前判断

- 现在 Part 2 不应该再被表述为“只能靠经典 CV 顶着跑”。更准确的说法是：
  1. baseline 已经保留；
  2. 更强的 classical segmentation 已经接入并拿到了更好的分类结果；
  3. BUSAT 工具箱本体已经到位，只差把 MATLAB 导出的掩膜接回 Python 流水线做正式对照。
- 当前剩下的 BUSAT 问题也变得更具体：不是下载不到工具箱，而是 Codex 当前无界面 shell 环境里启动 MATLAB CLI 会报 `Qt/neon` 相关错误，所以 BUSAT 批量导出需要在本机 MATLAB 会话中执行 `scripts/export_busat_masks.m`。

### 下一步

- 在本机 MATLAB 中运行 `scripts/export_busat_masks.m`，把 `autosegment` 掩膜导出到 `outputs/part2/busat_masks/`。
- 导出完成后，用 `python scripts/run_part2.py --strategies busat --busat-masks-dir outputs/part2/busat_masks` 复算一遍特征和分类指标，得到正式的 `BUSAT vs refined vs baseline` 对照表。
- 在此基础上继续补课程问答题 3/4：特征数量影响、分割误差影响。

## 2026-04-19

### 今日进展（Part 1 preparation）

- Part 1 的真实采集还没开始，但已经把“采完后直接接数据”的代码接口搭好，不需要等到 4 月 21 日之后再从零开工。
- 新增 `src/carotid_py/` 包，包含：
  - `config.py`：Part 1 本地数据与输出路径约定。
  - `data.py`：元数据 CSV 读取、图像路径解析、ROI 读取和中心搜索窗 fallback。
  - `segmentation.py`：`B-mode` 暗腔体分割 baseline 和 `Color Doppler` 彩色流动区域分割 baseline。
  - `quantify.py`：面积、等效直径、主/次轴、圆形度，以及与机器测量和文献范围对照的量化函数。
- 新增 `scripts/run_part1.py`，输入是 `metadata.csv + images/`，输出是 `outputs/part1/measurements.csv`、`segmentation_report.json`、可选 mask 和 overlay PNG。
- 新增 `docs/part1_metadata_template.csv` 和 `docs/part1_preparation.md`，把采集后需要填写的字段和推荐目录结构定下来了。
- `README.md` 已补 Part 1 使用说明，采集后只要把真实图像放到 `part1_data/images/`、把模板填写为 `part1_data/metadata.csv`，就可以直接跑。

### 接口设计要点

- 元数据里只强制要求 3 列：`sample_id`、`file_name`、`modality`。
- 为了满足课程里的物理量化，推荐补齐 `pixel_spacing_mm` 或 `pixel_spacing_x_mm / pixel_spacing_y_mm`。
- 为了提高分割稳定性，支持在元数据里直接写 `roi_x0/roi_y0/roi_x1/roi_y1`；如果采集后还来不及手工框 ROI，runner 会先用中心搜索窗跑第一版结果。
- 支持 `machine_diameter_mm`，后续可以直接和设备上手工测得的直径做误差对照。

### 当前验证

- 用两张本地合成图做了端到端 dry run：
  - 一张模拟 `B-mode` 暗腔体；
  - 一张模拟 `Color Doppler` 彩色流动区域。
- `python scripts/run_part1.py --metadata /tmp/bme1307_part1_synth/metadata.csv --images-dir /tmp/bme1307_part1_synth/images --save-masks --save-overlays` 已成功跑通，说明 metadata -> 分割 -> 量化 -> 输出文件 这条链路是通的。
- 这些合成结果只用于接口验证，不代表真实 Part 1 性能，也没有纳入仓库输出物。

### 额外处理

- `.gitignore` 已加入 `part1_data/` 和 `outputs/part1/`，避免 4 月 21 日之后的真实采集图像和对应输出误提交到 Git。

### 下一步

- 4 月 21 日采集完成后，先整理并填写 `part1_data/metadata.csv`。
- 第一轮先直接跑现有 baseline，看：
  1. 是否需要更严格的 ROI；
  2. `B-mode` 和 `Color Doppler` 哪条路更稳；
  3. 像素标定和机器直径记录是否完整。
- 跑完第一批真实图后，再基于真实成像风格调整 Part 1 分割策略，而不是现在提前拍脑袋过拟合。
