# MathProver — common tasks

MATHPROVER_HOME ?= $(CURDIR)
MATHPROVER_PROJECT_PATH ?= $(abspath ../lean-runtime-analysis)
NODE ?=
PROVER ?= auto

ifneq (,$(wildcard .env))
include .env
export
endif

export MATHPROVER_HOME MATHPROVER_PROJECT_PATH

.PHONY: help reindex ui dispatch agents-sync ui-check ui-build format

help:
	@echo "Targets:"
	@echo "  make reindex              Reindex Lean project graph (MATHPROVER_PROJECT_PATH)"
	@echo "  make ui                   Start SvelteKit workbench"
	@echo "  make dispatch NODE=...    Dispatch proof worker to Lean project"
	@echo "  make agents-sync          uv sync in agents/"
	@echo "  make ui-check             svelte-check"
	@echo "  make ui-build             vite build"
	@echo "  make format               prettier + ruff format"
	@echo ""
	@echo "Copy .env.example → .env and set MATHPROVER_PROJECT_PATH"

reindex:
	python3 scripts/reindex_project.py "$(MATHPROVER_PROJECT_PATH)"

ui: agents-sync
	cd mathprover-ui && pnpm install && pnpm dev

dispatch: agents-sync
	@test -n "$(NODE)" || (echo "Usage: make dispatch NODE=L661_coea_sel_measure_prob [PROVER=auto]" && exit 1)
	cd agents && uv run python dispatch.py \
		--root "$(MATHPROVER_PROJECT_PATH)" \
		--node "$(NODE)" \
		--prover "$(PROVER)"

agents-sync:
	cd agents && uv sync

ui-check:
	cd mathprover-ui && pnpm install && pnpm run check

ui-build:
	cd mathprover-ui && pnpm install && pnpm run build

format:
	cd mathprover-ui && pnpm dlx prettier --write .
	uvx ruff format agents scripts
