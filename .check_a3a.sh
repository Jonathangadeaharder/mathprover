#!/bin/bash
source "$HOME/.zshrc" 2>/dev/null
source "$HOME/.elan/env" 2>/dev/null
export PATH="$HOME/.elan/bin:$HOME/.local/bin:$PATH"
ROOT="$HOME/projects/lean-runtime-analysis"
cd "$ROOT" || exit 1
echo "== compile-check A3a core statement (expect: builds, only 'uses sorry' warning) =="
out=$(lake env lean proofs/A3a_core/attempt.lean 2>&1)
echo "lake env lean exit: $?"
echo "$out" | grep -iE 'error|sorry' | head
echo
echo "== aristotle CLI available? =="
if command -v aristotle >/dev/null 2>&1; then echo "aristotle: $(command -v aristotle)"; else echo "aristotle: not on PATH (try: uvx --from aristotlelib aristotle --help)"; fi
echo -n "ARISTOTLE_API_KEY set: "; [ -n "$ARISTOTLE_API_KEY" ] && echo yes || echo no
