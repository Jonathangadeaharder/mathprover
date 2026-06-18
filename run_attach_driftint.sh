#!/bin/zsh
cd /Users/jonathangadeaharder/projects/mathprover
export PATH="$HOME/.elan/bin:$HOME/.local/bin:$PATH"
[ -f "$HOME/.zshrc" ] && source "$HOME/.zshrc" 2>/dev/null
PY="$HOME/.local/share/uv/tools/aristotlelib/bin/python"
nohup "$PY" agents/aristotle_attach.py \
  --project-root /Users/jonathangadeaharder/projects/lean-runtime-analysis \
  --node M7_level_based_theorem_faithful \
  --project-id 586e38d0-93ac-45ca-a87b-f765236bd827 \
  --task-id dae37178-b835-4a03-b69d-245e1b752376 \
  --wait \
  > /tmp/driftint_attach.out 2>&1 &
echo "attach monitor pid $!"
