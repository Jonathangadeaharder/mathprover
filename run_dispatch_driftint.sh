#!/bin/zsh
cd /Users/jonathangadeaharder/projects/mathprover
export PATH="$HOME/.elan/bin:$HOME/.local/bin:$PATH"
[ -f "$HOME/.zshrc" ] && source "$HOME/.zshrc" 2>/dev/null
PY="$HOME/.local/share/uv/tools/aristotlelib/bin/python"   # python 3.14 with aristotlelib
nohup "$PY" agents/dispatch.py \
  --root /Users/jonathangadeaharder/projects/lean-runtime-analysis \
  --node M7_level_based_theorem_faithful \
  --prover aristotle --skip-verify \
  > /tmp/driftint_dispatch.out 2>&1 &
echo "dispatch pid $! (py=$PY)"
