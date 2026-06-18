#!/bin/bash
source "$HOME/.zshrc" 2>/dev/null
source "$HOME/.elan/env" 2>/dev/null
export PATH="$HOME/.elan/bin:$HOME/.local/bin:$PATH"
cd "$HOME/projects/mathprover/agents" || exit 1
python3 pipeline.py \
  --goal-file "$1" \
  --project-root "$HOME/projects/lean-runtime-analysis" \
  --max-depth "${2:-2}"
