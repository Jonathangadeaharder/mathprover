<script lang="ts">
  import Icon from './Icon.svelte';
  import { app } from '$lib/stores.svelte';
  import { FOUNDATIONS, NODE_BY_ID } from '$lib/data';
  import type { Foundation } from '$lib/types';

  const STATUS_META: Record<string, { label: string; color: string; desc: string }> = {
    AXIOM:      { label: 'Axiom',       color: '#fbbf24', desc: 'Cited verbatim; not mechanized end-to-end.' },
    PARTIAL:    { label: 'Partial',     color: '#60a5fa', desc: 'Mechanization in progress; some subgoals proved.' },
    MECHANIZED: { label: 'Mechanized',  color: '#34d399', desc: 'Fully proved in Lean (in project or Mathlib).' },
    PLANNED:    { label: 'Planned',     color: '#94a3b8', desc: 'Decomposition outlined; no Lean work yet.' },
  };

  const SUBSTATUS: Record<string, { color: string; label: string }> = {
    done:        { color: '#34d399', label: 'done' },
    in_progress: { color: '#60a5fa', label: 'in progress' },
    todo:        { color: '#64748b', label: 'todo' },
  };

  function gotoNode(id: string) {
    if (!NODE_BY_ID[id]) return;
    app.selectedNodeId = id;
    app.route = 'graph';
  }

  function computedPct(f: Foundation): number {
    if (f.subgoals.length === 0) return f.progress_pct;
    const done = f.subgoals.filter((s) => s.status === 'done').length;
    const partial = f.subgoals.filter((s) => s.status === 'in_progress').length;
    return Math.round(100 * (done + 0.5 * partial) / f.subgoals.length);
  }
</script>

<div class="found-grid">
  {#each FOUNDATIONS as f (f.id)}
    {@const meta = STATUS_META[f.status] ?? STATUS_META.PLANNED}
    {@const pct = computedPct(f)}
    <article class="found-card">
      <header>
        <div class="title-row">
          <h2>{f.name}</h2>
          <span class="status-pill" style="background: {meta.color}1f; color: {meta.color}; border: 1px solid {meta.color}40;">{meta.label}</span>
        </div>
        <div class="citation">
          <Icon name="page" size={12} />
          <span>{f.citation}{#if f.venue} · {f.venue}{/if}</span>
          {#if f.doi}
            <a href={`https://doi.org/${f.doi}`} target="_blank" rel="noopener">doi:{f.doi}</a>
          {/if}
        </div>
      </header>

      <p class="desc">{f.description}</p>

      <div class="progress">
        <div class="progress-bar">
          <div class="progress-fill" style="width: {pct}%; background: {meta.color};"></div>
        </div>
        <div class="progress-meta">
          <span class="pct">{pct}%</span>
          <span class="subgoal-count">{f.subgoals.filter((s) => s.status === 'done').length}/{f.subgoals.length} subgoals</span>
        </div>
      </div>

      {#if f.lean_name}
        <div class="lean-ref">
          <Icon name="bot" size={12} />
          <code>{f.lean_name}</code>
          {#if f.lean_file}<span class="loc">@ {f.lean_file}{#if f.lean_line}:{f.lean_line}{/if}</span>{/if}
        </div>
      {/if}

      {#if f.subgoals.length > 0}
        <div class="subgoals">
          <div class="subgoals-label">Mechanization decomposition</div>
          {#each f.subgoals as s (s.id)}
            {@const sm = SUBSTATUS[s.status]}
            <div class="subgoal">
              <span class="bullet" style="background: {sm.color};"></span>
              <span class="sg-desc">{s.desc}</span>
              {#if s.lean_name}<code class="sg-lean">{s.lean_name}</code>{/if}
              {#if s.effort}<span class="sg-effort">{s.effort}</span>{/if}
              <span class="sg-status" style="color: {sm.color};">{sm.label}</span>
            </div>
          {/each}
        </div>
      {/if}

      {#if f.used_in.length > 0}
        <div class="used-in">
          <span class="used-in-label">Used in:</span>
          {#each f.used_in as nid (nid)}
            {@const node = NODE_BY_ID[nid]}
            {#if node}
              <button class="used-link" onclick={() => gotoNode(nid)}>{node.paper_id} · {node.paper_name}</button>
            {:else}
              <span class="used-link missing">{nid}</span>
            {/if}
          {/each}
        </div>
      {/if}

      {#if f.notes}
        <div class="notes">
          <Icon name="sparkles" size={11} />
          <span>{f.notes}</span>
        </div>
      {/if}
    </article>
  {/each}

  {#if FOUNDATIONS.length === 0}
    <div class="empty">No foundations defined for this project. Add a <code>foundations</code> array to <code>.mathprover/graph.json</code>.</div>
  {/if}
</div>

<style>
  .found-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
    gap: 16px;
    padding: 16px 20px 24px;
    overflow-y: auto;
  }
  .found-card {
    background: var(--bg-2);
    border: 1px solid var(--border-1);
    border-radius: 10px;
    padding: 16px 18px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .found-card header { display: flex; flex-direction: column; gap: 6px; }
  .title-row { display: flex; align-items: center; gap: 10px; }
  h2 { margin: 0; font-size: 15px; color: var(--fg-1); font-weight: 600; }
  .status-pill {
    font-size: 10.5px;
    padding: 2px 8px;
    border-radius: 999px;
    font-weight: 500;
    text-transform: lowercase;
    letter-spacing: 0.02em;
  }
  .citation {
    display: flex; align-items: center; gap: 6px;
    font-size: 11.5px; color: var(--fg-3);
    flex-wrap: wrap;
  }
  .citation a { color: var(--fg-3); text-decoration: underline dotted; }
  .desc { font-size: 12.5px; color: var(--fg-2); line-height: 1.5; margin: 0; }
  .progress { display: flex; align-items: center; gap: 12px; }
  .progress-bar {
    flex: 1; height: 6px; background: var(--bg-3); border-radius: 3px; overflow: hidden;
  }
  .progress-fill { height: 100%; transition: width 200ms ease; }
  .progress-meta { display: flex; align-items: center; gap: 10px; font-size: 11px; }
  .pct { font-variant-numeric: tabular-nums; font-weight: 600; color: var(--fg-1); }
  .subgoal-count { color: var(--fg-3); }
  .lean-ref {
    display: flex; align-items: center; gap: 6px;
    font-size: 11.5px;
    background: var(--bg-3);
    padding: 5px 8px;
    border-radius: 4px;
    color: var(--fg-2);
  }
  .lean-ref code { font-family: var(--font-mono); color: var(--fg-1); }
  .lean-ref .loc { color: var(--fg-4); font-size: 10.5px; }
  .subgoals { border-top: 1px solid var(--border-1); padding-top: 10px; }
  .subgoals-label { font-size: 10.5px; color: var(--fg-3); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px; }
  .subgoal {
    display: grid;
    grid-template-columns: 10px 1fr auto auto auto;
    align-items: center;
    gap: 10px;
    padding: 4px 0;
    font-size: 11.5px;
  }
  .bullet { width: 8px; height: 8px; border-radius: 4px; }
  .sg-desc { color: var(--fg-2); }
  .sg-lean { font-family: var(--font-mono); color: var(--fg-3); font-size: 10.5px; }
  .sg-effort { color: var(--fg-3); font-family: var(--font-mono); font-size: 10.5px; }
  .sg-status { font-size: 10.5px; font-weight: 500; }
  .used-in { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; font-size: 11px; }
  .used-in-label { color: var(--fg-3); }
  .used-link {
    background: var(--bg-3); border: 1px solid var(--border-1); border-radius: 4px;
    padding: 3px 7px; cursor: pointer; color: var(--fg-2); font-size: 11px;
  }
  .used-link:hover { color: var(--fg-1); border-color: var(--border-2); }
  .used-link.missing { opacity: 0.5; cursor: default; }
  .notes {
    display: flex; align-items: flex-start; gap: 6px;
    font-size: 11.5px; color: var(--fg-3); font-style: italic;
    border-top: 1px dashed var(--border-1); padding-top: 8px;
  }
  .empty {
    grid-column: 1 / -1;
    padding: 40px;
    text-align: center;
    color: var(--fg-3);
    font-size: 13px;
  }
  .empty code { background: var(--bg-2); padding: 2px 6px; border-radius: 3px; font-family: var(--font-mono); }
</style>
