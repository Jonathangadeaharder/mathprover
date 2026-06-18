#!/bin/bash
# Load only the ARISTOTLE_API_KEY export from zshrc (avoid sourcing zsh syntax in bash).
# Never echo the key.
eval "$(grep -m1 '^[[:space:]]*export[[:space:]]\+ARISTOTLE_API_KEY=' "$HOME/.zshrc")"
if [ -z "$ARISTOTLE_API_KEY" ]; then echo "NO_KEY"; exit 1; fi
cd "$HOME/projects/mathprover/agents" || exit 1
python3 "$HOME/projects/mathprover/.aristotle_status.py" --check
