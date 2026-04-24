PYTHON ?= python3
VENV ?= .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: help setup setup-dev setup-fm check check-data part1 part2 part2-busat report-figures paper paper-clean docker-build docker-check docker-part1 docker-part2 docker-busat docker-notebook docker-part3

help:
	@printf '%s\n' \
		'BME1307 common commands:' \
		'  make setup          Create local venv and install core dependencies' \
		'  make setup-dev      Install notebook dependencies too' \
		'  make setup-fm       Install foundation-model dependencies too' \
		'  make check          Check Python imports' \
		'  make check-data     Check imports and expected local data paths' \
		'  make part1          Run Part 1 with ./data mounted locally' \
		'  make part2          Run Part 2 full/cv/refined baseline' \
		'  make part2-busat    Run Part 2 including pre-exported BUSAT masks' \
		'  make report-figures Generate report figures and copy them to paper/figures' \
		'  make paper          Build paper/main.tex with latexmk' \
		'  make docker-build   Build the core Docker image' \
		'  make docker-check   Check Docker imports and mounted data' \
		'  make docker-part2   Run Part 2 baseline in Docker' \
		'  make docker-busat   Run Part 2 with BUSAT masks in Docker' \
		'  make docker-notebook Start JupyterLab at http://localhost:8888/?token=bme1307' \
		'  make docker-part3   Build/run optional foundation-model image'

setup:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-core.txt

setup-dev: setup
	$(PIP) install -r requirements-dev.txt

setup-fm: setup
	$(PIP) install -r requirements-fm.txt

check:
	$(PY) scripts/check_environment.py --mode core

check-data:
	$(PY) scripts/check_environment.py --mode core --check-data

part1:
	PART1_METADATA_FILE=data/metadata.csv PART1_IMAGES_DIR=data $(PY) scripts/run_part1.py --save-masks --save-overlays

part2:
	$(PY) scripts/run_part2.py --strategies full cv refined

part2-busat:
	$(PY) scripts/run_part2.py --strategies full cv refined busat --busat-masks-dir outputs/part2/busat_masks

report-figures:
	$(PY) scripts/build_report_figures.py
	mkdir -p paper/figures
	cp outputs/report_figures/*.png paper/figures/

paper:
	@if ! command -v latexmk >/dev/null 2>&1; then \
		printf '%s\n' 'latexmk not found. Install MacTeX/TeX Live or upload paper/ to Overleaf.'; \
		exit 127; \
	fi
	cd paper && latexmk -pdf main.tex

paper-clean:
	@if command -v latexmk >/dev/null 2>&1; then \
		cd paper && latexmk -C main.tex; \
	fi
	rm -rf paper/build

docker-build:
	docker compose build check

docker-check:
	docker compose run --rm check

docker-part1:
	docker compose run --rm part1

docker-part2:
	docker compose run --rm part2

docker-busat:
	docker compose run --rm part2-busat

docker-notebook:
	docker compose up notebook

docker-part3:
	docker compose run --rm part3
