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

## 快速复现环境

推荐组员优先使用 Docker，避免不同系统上的 OpenCV、scikit-image、PyTorch 版本差异。完整部署说明见 [docs/environment_setup.md](docs/environment_setup.md)。

从零下载后，按下面顺序跑通主流程：

```bash
# 1. 克隆仓库
git clone https://github.com/ExusiaiHY/BME1307-spring-2026.git
cd BME1307-spring-2026

# 2. 放置外部数据
# Breast-ultrasound-samples/Ultrasound Samples/pathology.xlsx
# data/metadata.csv 和 data/2026-04-21 .../post/00000.jpg
# 如需 BUSAT 路线，还需 outputs/part2/busat_masks/*.png

# 3. 构建并检查 Docker 环境
make docker-build
make docker-check

# 4. 跑 Part 1 / Part 2
make docker-part1
make docker-part2
make docker-busat

# 5. 生成最终报告图表并同步到 paper/figures
make report-figures

# 6. 编译 IEEE LaTeX 论文（需要本机安装 MacTeX/TeX Live，或上传 paper/ 到 Overleaf）
make paper
```

如果不用 Docker，可使用本地虚拟环境跑核心流程：

```bash
make setup-dev
make check-data
make part1
make part2
make part2-busat
make report-figures
```

依赖文件分为三层：

- `requirements-core.txt`：Part 1 / Part 2 / 报告图表所需的 CPU 依赖。
- `requirements-dev.txt`：Notebook/Jupyter 依赖。
- `requirements-fm.txt`：Part 3 foundation-model 依赖，包括 PyTorch、OpenCLIP、Transformers。

`requirements.txt` 保留为当前开发环境的完整冻结快照，推荐新组员按上面的分层依赖安装。

## 论文工程

最终课程论文位于 [paper/](paper/)：

- [paper/main.tex](paper/main.tex)：IEEE-style 主文档。
- [paper/references.bib](paper/references.bib)：BibTeX 参考文献。
- [paper/figures/](paper/figures/)：报告图表副本，可直接编译或上传 Overleaf。
- [docs/report_figures_guide.md](docs/report_figures_guide.md)：图表用途和正文写作提示。

构建命令：

```bash
make report-figures
make paper
```

当前本机没有 `latexmk` 时，`make paper` 会提示安装 MacTeX/TeX Live；也可以直接把 `paper/` 上传到 Overleaf 编译。

## 协作说明

本项目使用 GitHub 进行团队协作。欢迎大家通过 Issue 和 Pull Request 参与讨论与贡献！

## 数据集与工具

- **BUSAT toolbox**: [下载链接](https://www.tamps.cinvestav.mx/~wgomez/downloads.html)
- **乳腺超声数据集**: [Breast-ultrasound-samples](https://github.com/Qian-IMMULab/Breast-ultrasound-samples)

## Part 1 Pipeline

Part 1 的真实采集数据位于 `data/`，也可以按同样格式替换为新的采集数据：

- 元数据模板：`docs/part1_metadata_template.csv`
- 说明文档：`docs/part1_preparation.md`
- 入口脚本：`scripts/run_part1.py`

推荐的数据目录：

```text
data/
  metadata.csv
  2026-04-21 .../post/00000.jpg
```

采集后把真实图像和 metadata 按模板整理，然后运行：

```bash
make part1
```

当前已实现：

- `B-mode` 颈动脉暗腔体分割 baseline
- `Color Doppler` 彩色流动区域分割 baseline
- ROI 接口：优先使用元数据中的 `roi_x0/roi_y0/roi_x1/roi_y1`，缺失时自动退回中心搜索窗
- 量化输出：面积、等效直径、主/次轴、圆形度，以及与机器测量直径和文献范围的对照

输出位于 `outputs/part1/`：`measurements.csv`、`segmentation_report.json`、可选的 mask / overlay PNG。

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

## Docker / Compose

```bash
# 构建核心镜像
make docker-build

# 检查依赖和数据挂载
make docker-check

# Part 2 baseline
make docker-part2

# Part 2 with exported BUSAT masks
make docker-busat

# JupyterLab: http://localhost:8888/?token=bme1307
make docker-notebook
```

Compose 默认使用仓库内的 `Breast-ultrasound-samples/Ultrasound Samples`、`data/`、`outputs/` 和 `.cache/`。如果路径不同，复制 `.env.example` 到 `.env` 后修改。

Part 3 的 SAM2 / OpenCLIP / BiomedCLIP 运行在可选 `fm` 镜像中，首次运行会下载模型权重：

```bash
make docker-part3
```
