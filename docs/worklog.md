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
