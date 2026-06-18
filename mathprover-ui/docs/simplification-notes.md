# Simplification Notes

## arrayProxy / recordProxy Tradeoff

**Location:** `src/lib/data.ts:24-60`

These Proxy wrappers provide live reactivity over `project.data` arrays/records. They're consumed as module-level exports (`NODES`, `NODE_BY_ID`, etc.) across many components.

**Why they exist:** Svelte 5's `$derived` works well for single-component reactivity, but these proxies allow cross-component reactivity without prop drilling or context passing. Components can import `NODES` directly and get live updates when `project.data` changes.

**Tradeoff:** Proxies add indirection and make debugging harder. However, removing them requires significant refactoring — either prop drilling through the component tree or converting all consumers to use `$derived` with explicit store subscriptions.

**Decision:** Keep for now. Document the tradeoff. Future refactoring PR could replace with explicit store subscriptions if the indirection becomes a maintenance burden.

---

## app.css Split Considerations

**Location:** `src/app.css` (~3100 lines)

Monolithic CSS file. Could split into per-component or per-section files imported via `@import` or Svelte `<style>` blocks.

**Why it's monolithic:** CSS custom properties (design tokens) are defined at `:root` and referenced throughout. Splitting would require either:

1. Importing all partials into a main file (adds indirection)
2. Moving component-specific styles into `<style>` blocks (duplicates design tokens)

**Current organization:** Well-organized by section comments (e.g., `/* Graph view */`, `/* Agent run view */`). Easy to navigate with Ctrl+F.

**Decision:** Keep monolithic. High effort to split, low immediate value. If the file grows beyond ~4000 lines or becomes hard to navigate, consider splitting design tokens into a separate file (`tokens.css`) and importing via `@import`.

---

## Summary of Completed Simplification

**Phase 1:** Dead code removal

- Removed `SAMPLE_PROJECT` / `ACTIVE_AGENT` dead proxies
- Removed unimplemented `force` layout option

**Phase 2:** Latent bug prevention

- Removed all 9 `all: unset` instances (global button reset handles normalization)

**Phase 3:** Inline style extraction

- Extracted ~50 static inline styles to utility classes
- PremisePicker: 14 → 0 remaining
- All other components: only dynamic styles remain

**Phase 4:** Configurability audit

- Removed untested light theme (103 lines of CSS)
- Removed untested density toggle (unused CSS variables)
- Dark theme is now the only theme

**Result:** ~250 lines removed, fewer untested code paths, cleaner codebase.
