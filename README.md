# BME1307 Spring 2026 — Medical Ultrasound Image Analysis

> 生物医学工程超声图像分析课程项目（2026春季）

## 项目简介

本项目包含 BME1307 课程的大作业内容，涉及超声图像的采集、分割、分类以及基础模型（Foundation Models）在医学超声图像上的应用评估。

## 任务概览

| Part | 内容 | 分值 |
|------|------|------|
| Part 1 | 超声图像采集与颈动脉分割 | 40 分 |
| Part 2 | 乳腺超声图像分类（BUSAT toolbox） | 30 分 |
| Part 3 | 基础模型驱动的分析 | 20 分 |
| Part 4 | 开放思考题 | 10 分 |

## 关键时间节点

- **报告截止**：2026/6/25 13:00
- **展示时间**：6/11 与 6/16 课堂，每组 20 分钟（16 分钟汇报 + 4 分钟 Q/A）

## 环境配置

建议使用项目自带的虚拟环境（通过 `requirements.txt` 安装依赖）：

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

## 协作说明

本项目使用 GitHub 进行团队协作。欢迎大家通过 Issue 和 Pull Request 参与讨论与贡献！

## 数据集与工具

- **BUSAT toolbox**: [下载链接](https://www.tamps.cinvestav.mx/~wgomez/downloads.html)
- **乳腺超声数据集**: [Breast-ultrasound-samples](https://github.com/Qian-IMMULab/Breast-ultrasound-samples)

## Part 2 Python 流水线

课程说明并没有把 Part 2 限制为“只能用经典 CV 分割”。当前仓库保留三层路线：

- `full`：把整张紧裁剪 ROI 当作病灶，作为最弱 baseline。
- `cv`：Otsu + morphology 的经典 CV baseline。
- `refined`：默认推荐路线，使用中心先验 seed + morphological Chan-Vese 细化边界。
- `busat`：如果已经在 MATLAB 里导出 `autosegment` 掩膜，可直接纳入同一套特征与分类评估。

```bash
# 默认跑 full / cv / refined 三路，数据放在 Breast-ultrasound-samples/Ultrasound Samples/
python scripts/run_part2.py

# 只看改进后的 classical segmentation
python scripts/run_part2.py --strategies refined --save-masks

# 如果已经从 MATLAB 导出了 BUSAT 掩膜
python scripts/run_part2.py --strategies busat --busat-masks-dir outputs/part2/busat_masks
```

输出位于 `outputs/part2/`：`features_full.csv`、`features_cv.csv`、`features_refined.csv`、`metrics.csv`、ROC 图、`segmentation_report.json`、可选的 mask PNG。

当前默认 5-fold 结果里，`refined + SVM` 的 AUC 达到 `0.924 ± 0.050`，`refined + RF` 的 Accuracy 达到 `0.875 ± 0.070`，都优于旧的 `cv` baseline。与此同时，`refined` 的平均前景占比从 `0.460` 压到 `0.243`，说明它确实在减少病灶周围低回声背景被一并吞入的问题。

## BUSAT 对接

BUSAT toolbox 已经安装在 MATLAB 路径中。为了避免把 MATLAB 和 Python 两套流程硬耦合，仓库提供了一个批量导出脚本：

```matlab
export_busat_masks
```

对应文件是 `scripts/export_busat_masks.m`。它会把 `autosegment` 结果导出为 `outputs/part2/busat_masks/<image_id>_mask.png`，然后 Python runner 就能用 `--strategies busat` 复算特征和分类指标，形成 `BUSAT vs refined CV vs baseline` 的直接对照。

说明：当前 Codex 所在的无界面 shell 环境里，MATLAB CLI 启动会触发本机 `Qt/neon` 相关报错，所以 BUSAT 的自动批跑脚本已经准备好，但需要在本机 MATLAB 会话里执行一次导出。

## Docker

镜像只装代码和依赖，数据集外挂：

```bash
# 构建
docker build -t bme1307-part2 .

# 运行（把本地数据集和输出目录挂进容器）
docker run --rm \
  -v "$(pwd)/Breast-ultrasound-samples/Ultrasound Samples":/data:ro \
  -v "$(pwd)/outputs":/app/outputs \
  bme1307-part2
```

`BUSAT_DATA_DIR` 环境变量可切换数据路径（容器内默认 `/data`）。
如果要在容器里复用预导出的 BUSAT 掩膜，可同时挂载并通过 `BUSAT_MASKS_DIR` 指向相应目录。
