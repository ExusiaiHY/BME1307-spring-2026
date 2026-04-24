# 2026-04-25 — 论文工程 + 部署复现流程

> 本次同步重点：IEEE LaTeX 论文工程、组员下载后的一键复现入口、README 更新、GitHub 同步准备。

## 1. 论文工程

- 新增 `paper/` 目录，作为最终课程论文工程：
  - `paper/main.tex`：IEEE conference-style 主文档草稿；
  - `paper/references.bib`：BibTeX 参考文献；
  - `paper/latexmkrc`：本地 `latexmk` 构建配置；
  - `paper/figures/`：论文可直接引用的图表副本。
- 论文正文已经覆盖：
  - Part 1：真实颈部超声采集、颈动脉分割与物理量化；
  - Part 2：乳腺超声分割、特征工程、三类分类器、特征数量影响和分割误差影响；
  - Part 3：SAM2 prompted segmentation、OpenCLIP/BiomedCLIP embedding 分类；
  - Part 4：开放思考题，核心观点为“采集感知 + 不确定性驱动”的医学图像处理闭环。

## 2. 图表工程

- `scripts/build_report_figures.py` 已修复 Matplotlib 缓存目录问题，固定使用项目内 `.cache/matplotlib` 和 `Agg` 后端。
- `make report-figures` 已通过，并会同时写入：
  - `outputs/report_figures/`
  - `paper/figures/`
- 当前论文图表包括 Part 1 直径汇总、Part 2 分割对比、特征数量影响、分割误差影响、Part 3 ROC 对比等。

## 3. README 全流程

总 README 已更新为下载后完整流程：

```bash
git clone https://github.com/ExusiaiHY/BME1307-spring-2026.git
cd BME1307-spring-2026
make docker-build
make docker-check
make docker-part1
make docker-part2
make docker-busat
make report-figures
make paper
```

- Docker/Compose 默认挂载 `Breast-ultrasound-samples/Ultrasound Samples`、`data/`、`outputs/`、`.cache/`。
- 如果路径不同，可复制 `.env.example` 为 `.env` 后修改。
- `make paper` 需要本机安装 MacTeX/TeX Live；没有本地 LaTeX 时，可直接把 `paper/` 上传到 Overleaf。

## 4. 验证状态

| 检查项 | 状态 |
|---|---|
| `make check-data` | 通过 |
| `scripts/check_environment.py --mode fm` | 通过 |
| `docker compose config --quiet` | 通过 |
| `make report-figures` | 通过 |
| `make paper` | 本机缺少 `latexmk`，已给出明确提示 |

## 5. 注意事项

- `paper/main.tex` 里的作者姓名和邮箱仍是占位符，提交前需要替换为最终组员信息。
- BUSAT 的 MATLAB 导出流程不放进 Docker；其他组员只需共享 `outputs/part2/busat_masks/*.png` 即可复算 BUSAT 路线。
- Part 3 foundation-model 镜像较大，首次运行需要下载 SAM2/OpenCLIP/BiomedCLIP 权重，建议复用 `.cache/part3/`。
