<script lang="ts">
  import Icon from './Icon.svelte';
  import { app } from '$lib/stores.svelte';
  import { DEFINITIONS, DEF_BY_ID, DEF_USED_BY, NODE_BY_ID } from '$lib/data';
  import { highlightLean } from '$lib/lean';
  import type { DefinitionKind } from '$lib/types';

  let query = $state('');
  let kindFilter = $state<DefinitionKind | 'all'>('all');
  let selectedId = $state<string | null>(app.selectedDefId);

  // Sync from cross-component navigation (e.g. NodeDetail "Uses definitions" click).
  $effect(() => {
    if (app.selectedDefId && app.selectedDefId !== selectedId) {
      selectedId = app.selectedDefId;
    }
  });
  $effect(() => {
    app.selectedDefId = selectedId;
  });

  const KIND_COLOR: Record<string, string> = {
    structure: '#a78bfa',
    def:       '#60a5fa',
    inductive: '#fb7185',
    abbrev:    '#94a3b8',
    instance:  '#34d399',
    class:     '#fbbf24',
    notation:  '#f472b6',
  };

  let filtered = $derived.by(() => {
    const q = query.trim().toLowerCase();
    return DEFINITIONS.filter((d) => {
      if (kindFilter !== 'all' && d.kind !== kindFilter) return false;
      if (!q) return true;
      return (
        d.name.toLowerCase().includes(q) ||
        d.lean_name.toLowerCase().includes(q) ||
        d.description.toLowerCase().includes(q)
      );
    });
  });

  let selected = $derived(selectedId ? DEF_BY_ID[selectedId] : null);

  function gotoNode(nid: string) {
    if (!NODE_BY_ID[nid]) return;
    app.selectedNodeId = nid;
    app.route = 'graph';
  }
</script>

<div class="defs-shell">
  <aside class="defs-list">
    <div class="defs-toolbar">
      <input
        class="defs-search"
        type="search"
        placeholder="Search definitions..."
        bind:value={query}
      />
      <select bind:value={kindFilter}>
        <option value="all">all kinds</option>
        <option value="structure">structure</option>
        <option value="def">def</option>
        <option value="inductive">inductive</option>
        <option value="abbrev">abbrev</option>
        <option value="instance">instance</option>
        <option value="class">class</option>
        <option value="notation">notation</option>
      </select>
    </div>
    <div class="defs-count">{filtered.length} / {DEFINITIONS.length} definitions</div>
    <div class="defs-scroll">
      {#each filtered as d (d.id)}
        <button
          class="def-row"
          class:active={selectedId === d.id}
          onclick={() => (selectedId = d.id)}
        >
          <span class="kind-pill" style="background: {KIND_COLOR[d.kind] ?? '#888'}1f; color: {KIND_COLOR[d.kind] ?? '#888'}; border-color: {KIND_COLOR[d.kind] ?? '#888'}40;">{d.kind}</span>
          <div class="def-row-main">
            <code class="lean-name">{d.lean_name}</code>
            <div class="def-name">{d.name}</div>
          </div>
          <span class="usage-count" title="theorems using this def">{(DEF_USED_BY[d.id] || []).length}</span>
        </button>
      {/each}
      {#if filtered.length === 0}
        <div class="empty">No matches.</div>
      {/if}
    </div>
  </aside>

  <main class="def-detail">
    {#if selected}
      {@const usedBy = DEF_USED_BY[selected.id] || []}
      <header>
        <span class="kind-pill big" style="background: {KIND_COLOR[selected.kind] ?? '#888'}1f; color: {KIND_COLOR[selected.kind] ?? '#888'}; border-color: {KIND_COLOR[selected.kind] ?? '#888'}40;">{selected.kind}</span>
        <h2>{selected.name}</h2>
        {#if selected.paper_label}
          <span class="paper-pill">{selected.paper_label}</span>
        {/if}
      </header>

      <p class="desc">{selected.description}</p>

      <section>
        <h3>Lean signature</h3>
        <pre class="code-block">{@html highlightLean(selected.signature ?? `-- ${selected.lean_name}`)}</pre>
      </section>

      <section class="meta">
        <h3>Metadata</h3>
        <dl>
          <dt>Lean name</dt><dd><code>{selected.lean_name}</code></dd>
          <dt>Lean file</dt><dd><code>{selected.lean_file}{selected.lean_line ? `:${selected.lean_line}` : ''}</code></dd>
          {#if selected.paper_file}
            <dt>Paper</dt><dd>{selected.paper_file}{selected.paper_section ? ` · ${selected.paper_section}` : ''}</dd>
          {/if}
        </dl>
      </section>

      {#if (selected.depends_on || []).length > 0}
        <section>
          <h3>Depends on</h3>
          <div class="dep-chips">
            {#each selected.depends_on || [] as did (did)}
              {@const dep = DEF_BY_ID[did]}
              {#if dep}
                <button class="dep-chip" onclick={() => (selectedId = did)}>
                  <span class="kind-pill" style="background: {KIND_COLOR[dep.kind] ?? '#888'}1f; color: {KIND_COLOR[dep.kind] ?? '#888'};">{dep.kind}</span>
                  <code>{dep.lean_name}</code>
                </button>
              {:else}
                <span class="dep-chip missing">{did}</span>
              {/if}
            {/each}
          </div>
        </section>
      {/if}

      {#if usedBy.length > 0}
        <section>
          <h3>Used in theorems ({usedBy.length})</h3>
          <div class="dep-chips">
            {#each usedBy as nid (nid)}
              {@const node = NODE_BY_ID[nid]}
              {#if node}
                <button class="dep-chip thm" onclick={() => gotoNode(nid)}>
                  <span class="pid">{node.paper_id}</span>
                  <span>{node.paper_name}</span>
                </button>
              {/if}
            {/each}
          </div>
        </section>
      {:else}
        <section>
          <h3>Used in theorems</h3>
          <div class="empty">No theorems reference this definition yet.</div>
        </section>
      {/if}
    {:else}
      <div class="def-detail-empty">
        <Icon name="page" size={28} />
        <h3>Pick a definition</h3>
        <p>Browse the list on the left. Definitions are the primitive notions the project depends on — structures like <code>SeparableGame</code>, abstractions like <code>PopulationProcess</code>, and the LBT preconditions (G1, G2, G3).</p>
      </div>
    {/if}
  </main>
</div>

<style>
  .defs-shell {
    display: grid;
    grid-template-columns: 380px 1fr;
    height: 100%;
    overflow: hidden;
  }
  .defs-list {
    border-right: 1px solid var(--border-1);
    display: flex;
    flex-direction: column;
    background: var(--bg-1);
    min-height: 0;
  }
  .defs-toolbar {
    padding: 12px 14px 8px;
    display: flex;
    gap: 8px;
    border-bottom: 1px solid var(--border-1);
  }
  .defs-search {
    flex: 1;
    background: var(--bg-2);
    border: 1px solid var(--border-1);
    color: var(--fg-1);
    border-radius: 5px;
    padding: 5px 10px;
    font-size: 12px;
    font-family: inherit;
  }
  .defs-toolbar select {
    background: var(--bg-2);
    border: 1px solid var(--border-1);
    color: var(--fg-1);
    border-radius: 5px;
    padding: 4px 6px;
    font-size: 11.5px;
  }
  .defs-count {
    font-size: 10.5px;
    color: var(--fg-3);
    padding: 6px 14px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .defs-scroll { flex: 1; overflow-y: auto; padding-bottom: 8px; }
  .def-row {
    all: unset;
    cursor: pointer;
    display: grid;
    grid-template-columns: auto 1fr auto;
    align-items: center;
    gap: 10px;
    padding: 8px 14px;
    border-left: 2px solid transparent;
    font-size: 12px;
  }
  .def-row:hover { background: var(--bg-2); }
  .def-row.active { background: var(--bg-2); border-left-color: var(--accent); }
  .def-row-main { min-width: 0; }
  .lean-name { font-family: var(--font-mono); font-size: 11.5px; color: var(--fg-1); display: block; }
  .def-name { font-size: 10.5px; color: var(--fg-3); margin-top: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .kind-pill {
    font-size: 9.5px;
    padding: 1px 6px;
    border-radius: 999px;
    border: 1px solid;
    font-weight: 500;
    text-transform: lowercase;
    letter-spacing: 0.02em;
  }
  .kind-pill.big { font-size: 10.5px; padding: 2px 9px; }
  .usage-count {
    font-family: var(--font-mono);
    font-size: 10.5px;
    color: var(--fg-3);
    background: var(--bg-3);
    padding: 1px 6px;
    border-radius: 4px;
  }
  .empty { padding: 24px 14px; color: var(--fg-3); font-size: 12px; }
  .def-detail {
    overflow-y: auto;
    padding: 20px 26px;
    display: flex;
    flex-direction: column;
    gap: 18px;
  }
  .def-detail header {
    display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  }
  .def-detail h2 { margin: 0; font-size: 18px; font-weight: 600; color: var(--fg-0); }
  .paper-pill {
    font-size: 10.5px;
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--bg-3);
    color: var(--fg-2);
  }
  .desc { font-size: 13px; color: var(--fg-1); line-height: 1.6; margin: 0; }
  .def-detail h3 {
    font-size: 10.5px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--fg-3);
    margin: 0 0 8px;
    font-weight: 600;
  }
  .code-block {
    background: var(--bg-2);
    border: 1px solid var(--border-1);
    border-radius: 5px;
    padding: 12px 14px;
    font-family: var(--font-mono);
    font-size: 12px;
    line-height: 1.55;
    color: var(--fg-1);
    overflow-x: auto;
    margin: 0;
    white-space: pre;
  }
  .meta dl { display: grid; grid-template-columns: max-content 1fr; gap: 6px 16px; font-size: 12px; margin: 0; }
  .meta dt { color: var(--fg-3); }
  .meta dd { color: var(--fg-1); margin: 0; }
  .meta code { font-family: var(--font-mono); font-size: 11.5px; color: var(--fg-1); }
  .dep-chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .dep-chip {
    all: unset; cursor: pointer;
    display: inline-flex; align-items: center; gap: 6px;
    background: var(--bg-2);
    border: 1px solid var(--border-1);
    border-radius: 4px;
    padding: 4px 9px;
    font-size: 11.5px;
    color: var(--fg-1);
  }
  .dep-chip:hover { border-color: var(--border-2); }
  .dep-chip code { font-family: var(--font-mono); font-size: 11px; }
  .dep-chip.thm .pid { color: var(--fg-3); font-family: var(--font-mono); font-size: 10.5px; }
  .dep-chip.missing { opacity: 0.5; cursor: default; }
  .def-detail-empty {
    margin: auto;
    text-align: center;
    color: var(--fg-3);
    max-width: 360px;
  }
  .def-detail-empty h3 { color: var(--fg-1); font-size: 13px; margin: 10px 0 8px; text-transform: none; letter-spacing: 0; }
  .def-detail-empty p { font-size: 12.5px; line-height: 1.55; margin: 0; }
  .def-detail-empty code { font-family: var(--font-mono); }
</style>
