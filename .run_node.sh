#!/bin/bash
source "$HOME/.zshrc" 2>/dev/null
source "$HOME/.elan/env" 2>/dev/null
export PATH="$HOME/.elan/bin:$HOME/.local/bin:$PATH"
cd "$HOME/projects/mathprover/agents" || exit 1
python3 pipeline.py --node "$1" --prompt "$2" --max-rounds "${3:-3}" --project-root "$HOME/projects/lean-runtime-analysis"
