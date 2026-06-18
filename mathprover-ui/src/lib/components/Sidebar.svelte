<script lang="ts">
  import Icon from './Icon.svelte';
  import { app, project } from '$lib/stores.svelte';
  import { NODES, NODE_BY_ID, FAILURES, FOUNDATIONS, DEFINITIONS } from '$lib/data';
  import { statusKey } from '$lib/lean';
  import type { Route, NodeStatus } from '$lib/types';

  const items: { id: Route; label: string; icon: string; live?: boolean }[] = [
    { id: 'graph',       label: 'Graph',         icon: 'graph' },
    { id: 'tracks',      label: 'Tracks',        icon: 'activity' },
    { id: 'frontier',    label: 'Frontier',      icon: 'target' },
    { id: 'definitions', label: 'Definitions',   icon: 'cog' },
    { id: 'paper-lean',  label: 'Paper ⇄ Lean',  icon: 'page' },
    { id: 'agents',     label: 'Agent runs',    icon: 'bot', live: true },
    { id: 'failures',   label: 'Failure shelf', icon: 'flask' },
    { id: 'foundations', label: 'Foundations',  icon: 'sparkles' },
  ];

  let stats = $derived.by(() => {
    let frontier = 0;
    NODES.forEach((n) => {
      const sk = statusKey(n.status);
      if (sk === 'READY' || sk === 'SORRIES' || sk === 'STUCK') {
        const deps = (n.depends_on || []).map((d) => NODE_BY_ID[d]).filter(Boolean);
        if (deps.length === 0 || deps.every((d) => statusKey(d.status) === 'PROVEN')) frontier++;
      }
    });
    return { graph: NODES.length, frontier, agents: project.data.activeAgent ? 1 : 0, failures: FAILURES.length };
  });

  let counts = $derived.by(() => {
    const c: Record<NodeStatus, number> = { PROVEN: 0, DISPROVEN: 0, SORRIES: 0, IN_PROGRESS: 0, STUCK: 0, DRAFT: 0, REJECTED: 0, READY: 0, BLOCKED: 0, UNEXPLORED: 0 };
    NODES.forEach((n) => { c[statusKey(n.status)]++; });
    return c;
  });

  const statusOrder: [NodeStatus, string][] = [
    ['PROVEN', 'proven'],
    ['DISPROVEN', 'disproven'],
    ['SORRIES', 'open sorries'],
    ['IN_PROGRESS', 'in progress'],
    ['STUCK', 'stuck'],
    ['DRAFT', 'draft'],
    ['REJECTED', 'rejected'],
    ['READY', 'ready'],
    ['BLOCKED', 'blocked'],
    ['UNEXPLORED', 'unexplored'],
  ];

  function badgeOf(id: Route): number | undefined {
    if (id === 'graph')    return stats.graph;
    if (id === 'tracks')   return stats.graph;
    if (id === 'frontier') return stats.frontier;
    if (id === 'failures') return stats.failures;
    if (id === 'foundations') return FOUNDATIONS.length;
    if (id === 'definitions') return DEFINITIONS.length;
    return undefined;
  }
</script>

<aside class="sidebar">
  <div class="section-label">Workspace</div>
  {#each items as it (it.id)}
    {@const badge = badgeOf(it.id)}
    <button
      class="nav-item"
      class:active={app.route === it.id}
      onclick={() => (app.route = it.id)}
    >
      <Icon name={it.icon} size={14} />
      <span>{it.label}</span>
      {#if it.live}<span class="pulse"></span>{/if}
      {#if badge !== undefined}<span class="badge">{badge}</span>{/if}
    </button>
  {/each}

  <div class="section-label">Status</div>
  {#each statusOrder as [k, label] (k)}
    {#if counts[k] > 0}
      <div class="status-row">
        <span class="status-dot" style="background: var(--st-{k.toLowerCase()});"></span>
        <span class="status-label">{label}</span>
        <span class="status-count">{counts[k]}</span>
      </div>
    {/if}
  {/each}

  <div class="sidebar-footer">
    <div class="sidebar-footer-row">
      <Icon name="sparkles" size={12} />
      <span>pydantic-ai · v0.3.4</span>
    </div>
    <div class="sidebar-footer-meta">mathlib4 · 4.18.0</div>
  </div>
</aside>

<style>
  .nav-item { all: unset; cursor: pointer; }
</style>
