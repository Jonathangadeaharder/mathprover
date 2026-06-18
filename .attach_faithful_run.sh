#!/bin/bash
eval "$(grep -m1 '^[[:space:]]*export[[:space:]]\+ARISTOTLE_API_KEY=' "$HOME/.zshrc")"
[ -z "$ARISTOTLE_API_KEY" ] && { echo NO_KEY; exit 1; }
source "$HOME/.elan/env" 2>/dev/null
export PATH="$HOME/.elan/bin:$PATH"
cd "$HOME/projects/mathprover/agents" || exit 1
echo "monitor start $(date)"
python3 aristotle_attach.py \
  --project-id 9baa8a33-341f-4152-bce2-ae581cdfed87 \
  --task-id 835d786c-937c-4764-8959-dd0feeab9940 \
  --node M7_level_based_theorem_faithful \
  --project-root "$HOME/projects/lean-runtime-analysis" \
  --wait --poll 60
echo "monitor end $(date) exit $?"
