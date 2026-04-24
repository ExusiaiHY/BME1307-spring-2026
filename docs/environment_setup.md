# 环境部署与组员复现指南

目标：组员拉取仓库后，优先用 Docker 复现实验；如果本机不方便装 Docker，再用本地 Python 虚拟环境。

## 1. 推荐目录结构

```text
BME1307/
├── Breast-ultrasound-samples/
│   └── Ultrasound Samples/
│       ├── 2.jpg ... 121.jpg
│       └── pathology.xlsx
├── data/
│   ├── metadata.csv
│   └── 2026-04-21 .../post/00000.jpg
├── outputs/
│   ├── part1/
│   ├── part2/
│   └── part3/
└── US Toolbox Ver. 2.0/        # 只在需要重新导出 BUSAT masks 时使用
```

数据集和 MATLAB BUSAT 工具箱不随仓库分发。`outputs/part2/busat_masks/` 可以由已跑过 MATLAB 的同学打包共享，其他组员拿到后即可在 Python/Docker 内复算 BUSAT 特征和分类。

## 2. Docker 快速开始

先安装 Docker Desktop 或 OrbStack，然后在仓库根目录运行：

```bash
make docker-build
make docker-check
```

如果本地数据路径和上面的推荐结构不同，复制 `.env.example` 为 `.env`，修改里面的宿主机路径：

```bash
cp .env.example .env
```

常用命令：

```bash
# Part 2：不依赖 MATLAB 的 full / cv / refined baseline
make docker-part2

# Part 2：包含已导出的 BUSAT masks
make docker-busat

# Part 1：使用 data/metadata.csv 和 data/ 下的采集图像
make docker-part1

# JupyterLab，浏览器打开 http://localhost:8888/?token=bme1307
make docker-notebook
```

如果系统没有 `make`，可以直接使用等价的 Docker Compose 命令：

```bash
docker compose build check
docker compose run --rm check
docker compose run --rm part2
docker compose run --rm part2-busat
docker compose up notebook
```

Part 3 的 foundation-model 流程需要下载 SAM2 / OpenCLIP / BiomedCLIP 权重，镜像也更大。只在需要复跑 Part 3 时执行：

```bash
make docker-part3
```

第一次运行 Part 3 会写入 `.cache/part3/`；后续复跑会复用缓存。若网络受限，可以由一台机器先下载缓存，再把 `.cache/part3/` 共享给其他组员。

## 3. 本地 Python 方案

如果不用 Docker：

```bash
make setup-dev
make check-data
```

核心实验只需要 `requirements-core.txt`；Notebook 需要 `requirements-dev.txt`；Part 3 foundation models 需要额外安装：

```bash
make setup-fm
```

常用本地运行命令：

```bash
make part2
make part2-busat
make part1
```

没有 `make` 时，本地命令可直接写成：

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python scripts/check_environment.py --mode core --check-data
.venv/bin/python scripts/run_part2.py --strategies full cv refined
```

## 4. BUSAT masks 的处理

BUSAT 的 `autosegment` 依赖 MATLAB 工具箱和 MATLAB runtime/license，不放进 Docker 镜像。需要重新导出 masks 时，在装有 MATLAB 和 `US Toolbox Ver. 2.0/` 的机器上运行：

```matlab
cd('/path/to/BME1307')
run('scripts/run_busat_export.m')
```

导出结果应位于：

```text
outputs/part2/busat_masks/<image_id>_mask.png
```

之后任意组员都可以用 `make docker-busat` 或 `make part2-busat` 复算 BUSAT 路线的特征和分类指标。

## 5. 故障排查

- `make docker-check` 找不到数据：确认 `Breast-ultrasound-samples/Ultrasound Samples/pathology.xlsx` 存在，或在 `.env` 中设置 `BUSAT_HOST_DATA_DIR`。
- `make docker-busat` 报缺少 mask：先确认 `outputs/part2/busat_masks/2_mask.png` 到 `121_mask.png` 已存在。
- Part 3 下载失败：先确认网络可访问 Hugging Face；也可以共享已有 `.cache/part3/`。
- Apple Silicon 机器运行 Docker 较慢：Part1/Part2 CPU 流程仍可接受；Part3 建议只复用已有 outputs 或在有 GPU/更强 CPU 的机器上跑。
