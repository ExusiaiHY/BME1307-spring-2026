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

```bash
# 本地跑：数据放在 Breast-ultrasound-samples/Ultrasound Samples/，输出落在 outputs/part2/
python scripts/run_part2.py --save-masks
```

输出位于 `outputs/part2/`：`features_full.csv`、`features_cv.csv`、`metrics.csv`、ROC 图、`segmentation_report.json`、可选的 mask PNG。

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
