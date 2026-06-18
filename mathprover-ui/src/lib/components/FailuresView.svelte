<script lang="ts">
  import StatusPill from './StatusPill.svelte';
  import Icon from './Icon.svelte';
  import { app } from '$lib/stores.svelte';
  import { FAILURES } from '$lib/data';

  let groupBy = $state<'approach' | 'node'>('approach');

  let totalTokens = $derived(FAILURES.reduce((a, f) => a + f.cost.tokens, 0));
  let totalUsd = $derived(FAILURES.reduce((a, f) => a + f.cost.usd, 0));
  let uniqueTargets = $derived(new Set(FAILURES.map((f) => f.target)).size);

  function show(id: string) {
    app.selectedNodeId = id;
    app.route = 'graph';
  }
</script>

<div class="pane-body">
  <div class="failures-header">
    <div>
      <div class="failures-summary">
        <strong class="fg-0">{FAILURES.length}</strong> recorded failed approaches across <strong class="fg-0">{uniqueTargets}</strong> theorems
      </div>
      <div class="failures-cost">
        {totalTokens.toLocaleString()} tokens · ${totalUsd.toFixed(2)} spent · avoid repeating these
      </div>
    </div>
    <div class="ml-auto flex-gap-sm">
      <button
        class="btn sm"
        style:background={groupBy === 'approach' ? 'var(--bg-active)' : 'var(--bg-2)'}
        onclick={() => (groupBy = 'approach')}
      >by approach</button>
      <button
        class="btn sm"
        style:background={groupBy === 'node' ? 'var(--bg-active)' : 'var(--bg-2)'}
        onclick={() => (groupBy = 'node')}
      >by theorem</button>
    </div>
  </div>

  <div class="failure-grid">
    {#each FAILURES as f (f.id)}
      <div class="fail-card">
        <div class="head">
          <Icon name="x" size={12} />
          <div class="target">{f.targetName}</div>
          <StatusPill status="STUCK" />
        </div>
        <div class="approach">{f.approach}</div>
        <div class="why">{f.why}</div>
        <div class="fail-counter-label">Counterexample / blocker</div>
        <div class="ctr">{f.counter}</div>
        <div class="meta">
          <span>{f.agent}</span>
          <span>{f.date}</span>
          <span>{f.cost.tokens.toLocaleString()} tok</span>
          <span>${f.cost.usd.toFixed(2)}</span>
          <button class="btn ghost sm fail-view-btn" onclick={() => show(f.target)}>
            view node
            <Icon name="arrow_right" size={10} />
          </button>
        </div>
      </div>
    {/each}
  </div>
</div>
