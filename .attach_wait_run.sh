#!/bin/bash
eval "$(grep -m1 '^[[:space:]]*export[[:space:]]\+ARISTOTLE_API_KEY=' "$HOME/.zshrc")"
[ -z "$ARISTOTLE_API_KEY" ] && { echo NO_KEY; exit 1; }
source "$HOME/.elan/env" 2>/dev/null
export PATH="$HOME/.elan/bin:$PATH"
cd "$HOME/projects/mathprover/agents" || exit 1
echo "monitor start $(date)"
python3 aristotle_attach.py \
  --project-id eeda73ed-3d18-4d4a-bf5e-3b1d95483eca \
  --task-id 96b968b5-43f8-48c6-8ef6-4964b82c692d \
  --node M7_level_based_theorem_corrected \
  --project-root "$HOME/projects/lean-runtime-analysis" \
  --wait --poll 60
echo "monitor end $(date) exit $?"
