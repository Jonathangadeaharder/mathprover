#!/bin/bash
source "$HOME/.zshrc" 2>/dev/null
source "$HOME/.elan/env" 2>/dev/null
export PATH="$HOME/.elan/bin:$HOME/.local/bin:$PATH"
export MATHPROVER_PROJECT_PATH="$HOME/projects/lean-runtime-analysis"
python3 -c 'import aristotlelib' 2>/dev/null && echo 'aristotlelib OK' || python3 -m pip install --quiet aristotlelib --break-system-packages 2>&1 | tail -1
cd "$HOME/projects/mathprover/agents" || exit 1
echo "== submit corrected LBT to aristotle at $(date) =="
python3 dispatch.py --root "$HOME/projects/lean-runtime-analysis" --node M7_level_based_theorem_corrected --prover aristotle --skip-verify
echo "dispatch exit: $? at $(date)"
