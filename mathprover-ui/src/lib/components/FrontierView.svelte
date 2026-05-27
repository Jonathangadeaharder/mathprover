<script lang="ts">
  import StatusPill from './StatusPill.svelte';
  import Icon from './Icon.svelte';
  import { app } from '$lib/stores.svelte';
  import { NODES, NODE_BY_ID, CHILDREN_BY_ID } from '$lib/data';
  import { statusKey } from '$lib/lean';
  import type { TheoremNode } from '$lib/types';

  type Candidate = { node: TheoremNode; deps: TheoremNode[]; depsProven: boolean; priority: number; tractability: number };

  let candidates = $derived.by<Candidate[]>(() => {
    return NODES
      .filter((n) => {
        const sk = statusKey(n.status);
        return sk === 'READY' || sk === 'SORRIES' || sk === 'FAILED' || sk === 'UNEXPLORED';
      })
      .map((n) => {
        const deps = (n.depends_on || []).map((d) => NODE_BY_ID[d]).filter(Boolean);
        const depsProven = deps.length === 0 || deps.every((d) => statusKey(d.status) === 'PROVEN');
        const tractability = depsProven ? 1.0 : 0.3;
        const priority = (n.importance || 0.5) * tractability;
        return { node: n, deps, depsProven, priority, tractability };
      })
      .sort((a, b) => b.priority - a.priority);
  });
  let ready = $derived(candidates.filter((c) => c.depsProven));
  let blocked = $derived(candidates.filter((c) => !c.depsProven));

  let totalChildren = $derived(ready.reduce((a, c) => a + (CHILDREN_BY_ID[c.node.id] || []).length, 0));

  function selectAndShowGraph(id: string) {
    app.selectedNodeId = id;
    app.route = 'graph';
  }

  function dispatchNode(id: string, e: MouseEvent) {
    e.stopPropagation();
    app.pendingDispatch = { nodeId: id, model: 'auto' };
  }
</script>

<div class="pane-body">
  <div class="frontier-list">
    <div style="margin-bottom: 16px; margin-top: 8px;">
      <div style="display: flex; align-items: baseline; gap: 12px; margin-bottom: 4px; flex-wrap: wrap;">
        <h2 style="margin: 0; font-size: 14px; font-weight: 600; white-space: nowrap; flex-shrink: 0;">Ready to attempt</h2>
        <span style="font-size: 12px; color: var(--fg-3);">
          all dependencies discharged · ranked by importance × tractability
        </span>
      </div>
      <p style="font-size: 12px; color: var(--fg-3); margin: 4px 0 0;">
        Sending an agent here is highest-leverage — every proof you close shrinks the dependency cones of {totalChildren} downstream theorems.
      </p>
    </div>

    <div class="frontier-head">
      <div></div>
      <div>Theorem</div>
      <div>Status</div>
      <div>Importance</div>
      <div>Confidence</div>
      <div></div>
    </div>

    {#each ready as c, i (c.node.id)}
      <div class="frontier-row" role="button" tabindex="0" onclick={() => selectAndShowGraph(c.node.id)} onkeydown={(e) => e.key === 'Enter' && selectAndShowGraph(c.node.id)}>
        <div class="rank">#{i + 1}</div>
        <div style="text-align: left;">
          <div class="ttl">{c.node.paper_name}</div>
          <div class="pid">{c.node.paper_id} · {c.node.lean_theorem} · {c.deps.length} dep{c.deps.length !== 1 ? 's' : ''}</div>
        </div>
        <div style="text-align: center;"><StatusPill status={c.node.status} /></div>
        <div>
          <div class="meter"><div class="meter-fill acc" style:width="{c.node.importance * 100}%"></div></div>
          <div style="font-size: 10.5px; color: var(--fg-3); text-align: center; font-family: var(--font-mono); margin-top: 3px;">{(c.node.importance * 100).toFixed(0)}</div>
        </div>
        <div>
          {#if c.node.confidence !== null && c.node.confidence !== undefined}
            <div class="meter">
              <div class="meter-fill"
                style:width="{c.node.confidence * 100}%"
                style:background={c.node.confidence > 0.7 ? 'var(--st-proven)' : c.node.confidence > 0.4 ? 'var(--st-sorries)' : 'var(--st-failed)'}
              ></div>
            </div>
            <div style="font-size: 10.5px; color: var(--fg-3); text-align: center; font-family: var(--font-mono); margin-top: 3px;">{(c.node.confidence * 100).toFixed(0)}</div>
          {:else}
            <div style="text-align: center; font-size: 10.5px; color: var(--fg-4); font-family: var(--font-mono);">—</div>
          {/if}
        </div>
        <div style="text-align: right;">
          <button class="btn primary sm" type="button" onclick={(e) => dispatchNode(c.node.id, e)}>
            <Icon name="play" size={10} />Dispatch
          </button>
        </div>
      </div>
    {/each}

    {#if blocked.length > 0}
      <div style="margin-top: 28px; margin-bottom: 12px;">
        <div style="display: flex; align-items: baseline; gap: 12px; margin-bottom: 4px; flex-wrap: wrap;">
          <h2 style="margin: 0; font-size: 14px; font-weight: 600; white-space: nowrap; flex-shrink: 0;">Blocked</h2>
          <span style="font-size: 12px; color: var(--fg-3);">waiting on upstream dependencies</span>
        </div>
      </div>
      {#each blocked as c (c.node.id)}
        {@const missing = c.deps.filter((d) => statusKey(d.status) !== 'PROVEN')}
        <button class="frontier-row" type="button" onclick={() => selectAndShowGraph(c.node.id)} style:opacity={0.7}>
          <div class="rank" style="color: var(--fg-4);">—</div>
          <div style="text-align: left;">
            <div class="ttl">{c.node.paper_name}</div>
            <div class="pid">blocked by: {missing.map((m) => m.paper_id).join(', ')}</div>
          </div>
          <div style="text-align: center;"><StatusPill status={c.node.status} /></div>
          <div>
            <div class="meter"><div class="meter-fill acc" style:width="{c.node.importance * 100}%"></div></div>
          </div>
          <div style="text-align: center; font-size: 10.5px; color: var(--fg-4); font-family: var(--font-mono);">—</div>
          <div style="text-align: right;">
            <span style="font-size: 10.5px; color: var(--fg-3); font-family: var(--font-mono);">
              {missing.length} blocker{missing.length > 1 ? 's' : ''}
            </span>
          </div>
        </button>
      {/each}
    {/if}
  </div>
</div>

<style>
  .frontier-row { cursor: pointer; }
</style>
