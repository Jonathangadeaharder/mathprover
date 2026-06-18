#!/bin/bash
source "$HOME/.zshrc" 2>/dev/null
source "$HOME/.elan/env" 2>/dev/null
export PATH="$HOME/.elan/bin:$HOME/.local/bin:$PATH"
export MATHPROVER_PROJECT_PATH="$HOME/projects/lean-runtime-analysis"
echo "== ensure aristotlelib importable =="
python3 -c 'import aristotlelib' 2>/dev/null && echo "already installed" || python3 -m pip install --quiet aristotlelib --break-system-packages 2>&1 | tail -2
python3 -c 'import aristotlelib; print("aristotlelib OK")' 2>&1 | tail -1
cd "$HOME/projects/mathprover/agents" || exit 1
echo "== submit A3a core to aristotle (cloud, async ~10min) at $(date) =="
python3 dispatch.py --node A3a_core --prover aristotle --skip-verify
echo "dispatch exit: $? at $(date)"
